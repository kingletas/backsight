"""The editor: files opened in tabs, and handed back exactly as they arrived.

FR-ED-07 and DD-9 are the whole design here. A file that has not been edited is
written from the bytes it was read as, so an untouched file is byte-identical by
construction rather than because the encoding round-tripped correctly. A file
that *has* been edited is written from the buffer, and nothing normalises it on
the way out — no reformatting, no reordering, no trailing newline added.
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")

from gi.repository import Adw, Gio, GLib, Graphene, Gtk, GtkSource

from backsight.app import (
    block_labels,
    close_dialog,
    completion,
    gutter_marks,
    occurrences,
    run_marks,
    tab_marks,
)
from backsight.app.annotation_lane import Annotation, Lane
from backsight.app.change_map import ChangeMap, Mark
from backsight.app.find import Search
from backsight.app.leading import keep_the_row
from backsight.app.theme import tokens
from backsight.engine.hcl.document import Document
from backsight.engine.insight.file_status import FileStatus
from backsight.engine.layout.tabs import OpenTab, Scope, Selection, changed_lines
from backsight.engine.text import handling, pairs
from backsight.engine.workspace import watching

# GtkSourceView 5.12 ships a Terraform definition covering `.tf`, `.tfvars` and
# `.hcl`. Ours only has to exist if that one turns out to have gaps.
LANGUAGE = "terraform"

# Deep enough to undo a refactor, bounded so a long session cannot grow forever.
UNDO_LEVELS = 1000


class Page:
    """One open file."""

    def __init__(
        self,
        path: Path,
        on_run_file=None,
        settings=None,
        schema=None,
        on_finding=None,
        on_finding_menu=None,
    ) -> None:
        self.settings = settings
        # The provider reads this when it is asked, so a schema built after the
        # file was opened still reaches it.
        self.schema = schema
        self.document = Document.read(path)
        # What the file looked like when it was read, so a change made outside
        # the editor can be noticed before anything is written over it.
        self.stamp = watching.Stamp.of(path)
        manager = GtkSource.LanguageManager.get_default()
        self.buffer = GtkSource.Buffer(language=manager.get_language(LANGUAGE))
        self.buffer.set_max_undo_levels(UNDO_LEVELS)
        self.buffer.set_enable_undo(True)
        # Loading the file is not an edit, so it must not be undoable — an undo
        # that empties a file the user has not touched is a data-loss bug.
        self.buffer.begin_irreversible_action()
        self.buffer.set_text(self.document.text)
        self.buffer.end_irreversible_action()
        self.buffer.set_modified(False)

        self.view = GtkSource.View(buffer=self.buffer)
        self.view.set_monospace(True)
        self.view.set_left_margin(8)
        self.view.set_top_margin(6)
        # Indentation is read from the file rather than imposed on it. Opening
        # somebody's tab-indented module and inserting spaces because a setting
        # said so is the same damage as reformatting on save.
        # The setting is only the fallback: a file with nothing to read from —
        # a new one, or one line long — has no indentation to detect.
        width = int(settings.get("editor.tab_size", 4)) if settings is not None else 4
        found = handling.detect_indentation(self.document.text, default_width=width)
        self.indentation = found
        self.line_ending = handling.detect_line_ending(self.document.text)
        apply_display(self.view, indentation=found, settings=settings)
        self.buffer.connect("insert-text", self._closing_the_pair)
        suggesting = settings.get("analysis.value_completion", True) if settings else True
        self.completion = completion.install(self.view, lambda: self.schema) if suggesting else None
        self.lane = Lane(self.view)
        # The last thing to go when everything else is turned off.
        self.view.add_css_class("tf-buffer")
        # The row, in pixels, from the font that is actually loaded. The
        # stylesheet cannot do this: see `app/leading.py`.
        keep_the_row(self.view, tokens.LINE["code"])
        self.change_map = ChangeMap(on_go_to=self.go_to_line)
        self.change_map.set_visible(False)
        # The strip says which part of the file you are looking at, so it has to
        # be told when that moves. Scrolling is the only thing that changes it
        # without anything else in the editor being asked.
        scrolling = self.view.get_vadjustment()
        if scrolling is not None:
            scrolling.connect("value-changed", lambda *_: self.tell_the_map_where_we_are())
        # A mark is a thing you can point at: a click explains the finding on
        # that line and a right-click opens the menu that is about it. The
        # mouse inventory has said so since it was written and neither worked.
        self.marks, self.spine = gutter_marks.install(
            self.view, on_activate=on_finding, on_menu=on_finding_menu
        )
        # The fold column, held whether or not folding exists, and the
        # outlines on whatever word is selected.
        self.occurrences = occurrences.install(self.view)
        # The two labels on a block header, told apart by the tree. The
        # language spec captures both of them as one span, so no colour scheme
        # can separate them — see app/block_labels.py.
        self.labels = block_labels.install(self.view)
        # A test file's runs are marked in the same gutter. The two never
        # compete: a `.tf` file has no runs and a `.tftest.hcl` has no plan.
        self.run_marks = run_marks.install(self.view, on_activate=on_run_file)
        self.search = Search(self.buffer)
        self.show_bands = True
        # Every annotation layer toggles on its own. Hints are off
        # until asked for, like everything else in that list.
        self.show_hints = False
        # Off by default, for anyone who finds a line above every
        # block noisy. Which is most people, most of the time.
        self.show_lens = False
        self._verdicts: list = []
        self._hints: list = []
        self._lenses: list = []
        self.search = Search(self.view.get_buffer())
        self.hovers_shown = bool(
            settings.get("editor.hover_popups", True) if settings is not None else True
        )

    def tell_the_map_where_we_are(self) -> None:
        """Which lines are on screen, for the strip's viewport rectangle."""
        seen = self.view.get_visible_rect()
        top = self.view.get_iter_at_location(0, seen.y)
        bottom = self.view.get_iter_at_location(0, seen.y + seen.height)
        first = top[1].get_line() + 1 if top[0] else 1
        last = bottom[1].get_line() + 1 if bottom[0] else self.buffer.get_line_count()
        self.change_map.looking_at(first, max(first, last))

    @property
    def path(self) -> Path:
        return self.document.path

    def replace_all(self, after: str) -> bool:
        """Rewrites this page's whole content, touching only what differs."""
        from backsight.app.editing import replace_whole  # noqa: PLC0415

        return replace_whole(self.buffer, after)

    def select_lines(self, first: int, last: int) -> None:
        """Selects whole lines, from the start of one to the end of the other."""
        buffer = self.view.get_buffer()
        found, start = buffer.get_iter_at_line(max(0, first - 1))
        if not found:
            return
        _found, end = buffer.get_iter_at_line(min(last - 1, buffer.get_line_count() - 1))
        # `forward_to_line_end` moves to the *next* line's end when it is
        # already at one — which an empty line always is. So it is only called
        # where there is something on the line to move past.
        if not end.ends_line():
            end.forward_to_line_end()
        buffer.select_range(start, end)
        self.view.scroll_to_iter(start, 0.2, False, 0.0, 0.0)

    def select_next_occurrence(self) -> bool:
        """Moves the selection to the next place the selected word appears.

        With nothing selected it takes the word under the caret first, which is
        what makes the first press of the key do something. It wraps, because a
        search that stops at the end of the file is one you press twice for no
        reason.
        """
        buffer = self.buffer
        bounds = buffer.get_selection_bounds()
        if not bounds:
            caret = buffer.get_iter_at_mark(buffer.get_insert())
            start, end = caret.copy(), caret.copy()
            if not start.starts_word():
                start.backward_word_start()
            if not end.ends_word():
                end.forward_word_end()
            if start.equal(end):
                return False
            buffer.select_range(start, end)
            return True

        start, end = bounds
        word = buffer.get_text(start, end, False)
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
        found = occurrences.places(text, word)
        if len(found) < 2:
            return False
        here = start.get_offset()
        after = next((one for one in found if one[0] > here), found[0])
        buffer.select_range(
            buffer.get_iter_at_offset(after[0]), buffer.get_iter_at_offset(after[1])
        )
        self.view.scroll_to_mark(buffer.get_insert(), 0.1, False, 0.0, 0.5)
        return True

    def go_to_line(self, line: int) -> None:
        """Puts the caret at the start of a line and scrolls it into view.

        Lines are 1-based here, as they are everywhere a person reads one; the
        buffer counts from zero.
        """
        buffer = self.view.get_buffer()
        wanted = max(0, min(line - 1, buffer.get_line_count() - 1))
        found, position = buffer.get_iter_at_line(wanted)
        if not found:
            return
        buffer.place_cursor(position)
        self.view.scroll_to_iter(position, 0.2, False, 0.0, 0.0)

    @property
    def modified(self) -> bool:
        return self.buffer.get_modified()

    def content(self) -> bytes:
        """What saving this page would write.

        An unmodified page gives back the bytes it was read as. Nothing about the
        buffer's encoding can then affect a file nobody edited.
        """
        if not self.modified:
            return self.document.data
        text = self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), True)
        return text.encode("utf-8")

    def save(self, *, trim: bool = True, final_newline: bool = True) -> None:
        """Writes the file, tidied by the two rules that cannot change meaning.

        The buffer is rewritten to match what was written, so the tab is not
        left holding text that differs from the file on disk — and the caret
        stays where the person left it rather than jumping to the top.
        """
        data = self.content()
        if self.modified and (trim or final_newline):
            text = handling.on_save(data.decode("utf-8"), trim=trim, final_newline=final_newline)
            tidied = text.encode("utf-8")
            if tidied != data:
                self._replace_keeping_the_caret(text)
                data = tidied
        Document(path=self.path, data=data).write()
        self.document = Document.read(self.path)
        self.stamp = watching.Stamp.of(self.path)
        self.buffer.set_modified(False)

    def _closing_the_pair(self, buffer, where, text: str, length: int) -> None:
        """Closes a bracket or a quote as it is typed, when that helps.

        Only single characters typed by a person: a paste, a snippet and a
        format all arrive here too, and closing brackets inside them would
        corrupt the text rather than help anybody.
        """
        get = self.settings.get if self.settings is not None else (lambda _k, d=None: d)
        if length != 1 or len(text) != 1 or not get("editor.close_brackets", True):
            return
        line_start = buffer.get_iter_at_line(where.get_line())[1]
        line_end = where.copy()
        if not line_end.ends_line():
            line_end.forward_to_line_end()
        said = pairs.typed(
            text,
            before=buffer.get_text(line_start, where, False),
            after=buffer.get_text(where, line_end, False),
        )
        if said.is_nothing:
            return
        # Deferred: the buffer is mid-insert, so nothing may edit it from here.
        GLib.idle_add(self._finish_the_pair, said, priority=GLib.PRIORITY_HIGH)

    def _finish_the_pair(self, said) -> bool:
        buffer = self.buffer
        caret = buffer.get_iter_at_mark(buffer.get_insert())
        if said.step_over:
            # It was inserted anyway, so there are two now. Deleting the one in
            # front leaves the caret past a single closer, which is what typing
            # it should have felt like.
            after = caret.copy()
            if after.ends_line():
                return False
            after.forward_char()
            if buffer.get_text(caret, after, False) == said.character:
                buffer.delete(caret, after)
            return False
        buffer.insert(caret, said.insert)
        back = buffer.get_iter_at_mark(buffer.get_insert())
        back.backward_chars(len(said.insert))
        buffer.place_cursor(back)
        return False

    def reload_from_disk(self) -> None:
        """Takes what is on disk now, as one undoable change.

        Undoable on purpose: somebody who reloads and then realises they wanted
        their own version gets it back with one key.
        """
        self.document = Document.read(self.path)
        self.stamp = watching.Stamp.of(self.path)
        self._replace_keeping_the_caret(self.document.text)
        self.buffer.set_modified(False)

    def text(self) -> str:
        buffer = self.buffer
        return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

    def _replace_keeping_the_caret(self, text: str) -> None:
        """Rewrites the buffer as one undo, and puts the caret back."""
        buffer = self.buffer
        where = buffer.get_iter_at_mark(buffer.get_insert())
        line, column = where.get_line(), where.get_line_offset()
        buffer.begin_user_action()
        buffer.set_text(text)
        buffer.end_user_action()
        line = max(0, min(line, buffer.get_line_count() - 1))
        found, position = buffer.get_iter_at_line(line)
        if found:
            position.forward_chars(min(column, position.get_chars_in_line() - 1))
            buffer.place_cursor(position)


# What a preview tab shows instead of the italics the design asks for.
PREVIEW_ICON = "view-reveal-symbolic"
PREVIEW_NOTE = "Preview — editing it, or a double click, keeps it open"


class Editor(Adw.Bin):
    """Every open file, in tabs."""

    def __init__(
        self,
        theme=None,
        on_run_file=None,
        settings=None,
        schema=None,
        on_new_file=None,
        on_empty=None,
        on_finding=None,
        on_finding_menu=None,
    ) -> None:
        self._on_run_file = on_run_file
        self._on_new_file = on_new_file
        self._on_empty = on_empty
        self._on_finding = on_finding
        self._on_finding_menu = on_finding_menu
        self.settings = settings
        self.schema = schema
        # What a new page inherits, so a toggle applies to files opened later.
        self._view_state: dict[str, bool] = {}
        # When each file was last looked at, for sorting by recency. A counter
        # rather than a clock: two files opened in the same millisecond still
        # have an order, and nothing here depends on the wall time.
        self._touched: dict[Path, int] = {}
        self._touches = 0
        # Closed tabs, newest last. Kept so a mis-click costs one keystroke.
        self._closed: list[Path] = []
        # The one tab a single click reuses, or None when there is none.
        self._preview: Path | None = None
        super().__init__()
        self.pages: dict[Path, Page] = {}
        self._theme = theme
        self._statuses: dict[Path, FileStatus] = {}
        self.letters = False
        self._tabs = Adw.TabView(vexpand=True)
        bar = Adw.TabBar(view=self._tabs, autohide=False)
        # Tabs size to content with a cap. libadwaita stretches them to fill the
        # bar by default, which put two files at nearly 500px each.
        bar.set_expand_tabs(False)

        # The new-tab button goes **after the last tab, on its own**. It was
        # drawn inside the active tab, where it reads as part of the file's
        # name rather than as a control of its own.
        new_tab = Gtk.Button(icon_name="tab-new-symbolic")
        new_tab.add_css_class("flat")
        new_tab.set_tooltip_text("New file")
        new_tab.connect("clicked", lambda *_: self.new_file())
        # Overflow is a chevron that opens a list, never a strip that scrolls
        # with no affordance. Twelve open files is an ordinary afternoon.
        overflow = Gtk.Button(icon_name="pan-down-symbolic")
        overflow.add_css_class("flat")
        overflow.set_tooltip_text("All open files")
        overflow.connect("clicked", lambda *_: self.show_every_tab())
        after = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        after.append(new_tab)
        after.append(overflow)
        after.add_css_class("tf-tab-actions")
        bar.set_end_action_widget(after)
        self._overflow = overflow
        # Small, expected, and its absence is noticed at once by anyone coming
        # from another editor. The bar has no signal for it, so the
        # page is found from where the pointer was.
        middle = Gtk.GestureClick(button=2)
        middle.connect("released", self._on_middle_click)
        bar.add_controller(middle)
        self._tab_bar = bar

        layout = Adw.ToolbarView()
        layout.add_top_bar(bar)
        layout.set_content(self._tabs)
        self._layout = layout
        # The overview is what the overflow chevron opens: every open file as a
        # list, rather than a strip that scrolls with nothing saying it does.
        overview = Adw.TabOverview(view=self._tabs, child=layout, enable_new_tab=True)
        overview.connect("create-tab", lambda *_: self._new_from_overview())
        self._overview = overview
        self.set_child(overview)
        self._tabs.connect("close-page", self._on_close)

    def setting(self, key: str, default=None):
        """One setting, or its default when the editor was built without any."""
        return self.settings.get(key, default) if self.settings is not None else default

    def open(self, path: Path, *, preview: bool = False) -> Page:
        """Shows a file, reusing its tab if it is already open.

        `preview` is the single-click behaviour: one reused tab rather
        than a new one per click. Browsing a repository you do not know is the
        case it exists for — twenty clicks should not leave twenty tabs.

        A file already open is focused, never previewed: it has already been
        opened deliberately and a preview would demote it.
        """
        path = Path(path).resolve()
        existing = self.pages.get(path)
        if existing is not None:
            self._tabs.set_selected_page(self._page_for(existing))
            self._touch(existing)
            return existing

        # **Read it before anything is closed.** A file that cannot be shown
        # without damaging it is refused, and refusing must not cost somebody
        # the file they were looking at: closing the previous preview first
        # meant an unreadable file took a readable one with it, and left the
        # editor emptier than it found it.
        page = Page(
            path,
            on_run_file=self._on_run_file,
            settings=self.settings,
            schema=self.schema,
            on_finding=self._on_finding,
            on_finding_menu=self._on_finding_menu,
        )

        if preview and self._preview is not None and self._preview in self.pages:
            # The previous preview goes, so the new one takes its place rather
            # than adding to a row of them.
            going = self.pages[self._preview]
            self._tabs.close_page(self._page_for(going))

        self._apply_view_state(page)
        if self._theme is not None:
            page.change_map.use_colours(self._theme.colours())
        if self._theme is not None:
            self._theme.follow(page.buffer)
        # The strip sits beside the file, outside the scroller: it shows the
        # whole file at once, so scrolling must not move it.
        beside = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        beside.append(_scrolled(page.view))
        beside.append(page.change_map)
        tab = self._new_tab(beside)
        tab.set_tooltip(str(path))
        tab.page = page
        self.pages[path] = page
        self._tabs.set_selected_page(tab)
        self._touch(page)
        self._preview = path if preview else self._preview
        if self.setting("files.promote_preview_on", "edit") == "edit":
            page.buffer.connect("changed", lambda *_a, p=path: self.promote(p))
        page.buffer.connect("modified-changed", lambda *_: self._retitle(tab, page))
        self._retitle_all()
        return page

    @property
    def current(self) -> Page | None:
        tab = self._tabs.get_selected_page()
        return getattr(tab, "page", None) if tab is not None else None

    def what_happened_to_it(self, page) -> str:
        """Whether one open file changed on disk since it was read."""
        return watching.what_happened(page.stamp, page.path)

    def reapply_display(self) -> None:
        """Pushes the current settings into every open page, live."""
        hovers = bool(self.setting("editor.hover_popups", True))
        for page in self.pages.values():
            apply_display(page.view, indentation=page.indentation, settings=self.settings)
            page.hovers_shown = hovers

    def save_current(self, *, trim: bool = True, final_newline: bool = True) -> None:
        page = self.current
        if page is not None:
            page.save(trim=trim, final_newline=final_newline)

    def show_verdicts(self, verdicts) -> None:
        """Hangs each verdict on the line of the file it belongs to.

        The gutter mark and the band are separate layers on purpose. Turning the
        bands off leaves the marks, which is what survives when everything else is off.
        """
        from backsight.engine.insight.verdicts import in_file  # noqa: PLC0415

        for page in self.pages.values():
            page._verdicts = in_file(verdicts, page.path)
            page.marks.show(page._verdicts)
            page.spine.show(page._verdicts)
            self._redraw(page)

    def show_test_results(self, results, workspace: Path | None = None) -> None:
        """Marks every open test file with how its runs last went."""
        for page in self.pages.values():
            if not page.path.name.endswith(".tftest.hcl"):
                continue
            relative = _relative(page.path, workspace)
            page.run_marks.show(page.document.data, results, relative)

    def show_hints(self, hints) -> None:
        """Resolved values and expansion, on the lines that declare them."""
        from backsight.engine.insight.hints import in_file as hints_in_file  # noqa: PLC0415

        for page in self.pages.values():
            page._hints = hints_in_file(hints, page.path)
            self._redraw(page)

    def show_lenses(self, lenses, source_map) -> None:
        """The code lens, on the line each resource block starts."""
        from backsight.engine.insight.lens import in_file as lenses_in_file  # noqa: PLC0415

        for page in self.pages.values():
            page._lenses = lenses_in_file(lenses, str(page.path), source_map)
            self._redraw(page)

    def set_lens_shown(self, shown: bool) -> None:
        for page in self.pages.values():
            page.show_lens = shown
            self._redraw(page)

    def set_bands_shown(self, shown: bool) -> None:
        """Every annotation layer is independently toggleable."""
        for page in self.pages.values():
            page.show_bands = shown
            self._redraw(page)

    def set_hints_shown(self, shown: bool) -> None:
        for page in self.pages.values():
            page.show_hints = shown
            self._redraw(page)

    def set_change_map_shown(self, shown: bool) -> None:
        for page in self.pages.values():
            page.change_map.set_visible(shown)
            self._redraw_map(page)

    def _redraw_map(self, page: Page) -> None:
        """The strip reads the same verdicts the gutter does.

        A mark is the block, not the line the verdict hangs off — a bar the
        height of the resource is what makes the strip a map of the file rather
        than a scatter of ticks beside it.
        """
        lines = page.view.get_buffer().get_line_count()
        page.change_map.show(
            [
                Mark(line=v.block.start, tone=v.tone, last_line=v.block.stop - 1)
                for v in page._verdicts
            ],
            lines=lines,
        )
        page.tell_the_map_where_we_are()

    def _redraw(self, page: Page) -> None:
        """One lane, fed by whichever annotations are turned on.

        The three kinds are declared rather than mixed, because when each one
        is drawn is a different rule: a lens is always shown, an explanation
        only for the worst thing on the screenful, a resolved value only on the
        line the caret is on.
        """
        annotations: list[Annotation] = []
        if page.show_bands:
            annotations += [Annotation.of(v) for v in page._verdicts]
        if page.show_hints:
            annotations += [
                Annotation(line=h.line, text=h.text, tone=h.tone, kind="hint") for h in page._hints
            ]
        if page.show_lens:
            # Where a verdict already sits on the line, the lens drops its own
            # copy of the plan action rather than saying it twice.
            spoken = {item.line for item in annotations}
            annotations += [
                Annotation(
                    line=lens.line,
                    text=lens.without_action if lens.line in spoken else lens.text,
                    tone="hint",
                    kind="lens",
                )
                for lens in page._lenses
            ]
        page.lane.show(annotations)
        self._redraw_map(page)

    def show_statuses(
        self, statuses: dict[Path, FileStatus], *, letters: bool | None = None
    ) -> None:
        """What git and the plan say about each open file."""
        self._statuses = dict(statuses)
        if letters is not None:
            self.letters = letters
        self._retitle_all()

    def _status_for(self, page: Page) -> FileStatus:
        """The saved state is authoritative except for unsaved, which is local."""
        found = self._statuses.get(page.path.resolve())
        base = found or FileStatus(path=page.path.resolve())
        return FileStatus(
            path=base.path,
            vcs=base.vcs,
            impact=base.impact,
            unsaved=page.modified,
            unreadable=base.unreadable,
            counts=base.counts,
        )

    def _retitle(self, tab: Adw.TabPage, page: Page) -> None:
        """Every slot a tab has, refreshed together so none of them lags."""
        status = self._status_for(page)
        tab.set_title(
            tab_marks.title(
                self._name_for(page),
                status,
                letters=self.letters,
                unsaved=str(self.setting("tabs.indicators.unsaved", "dot")),
            )
        )
        tab.set_tooltip(tab_marks.tooltip(str(page.path), status))
        if page.path == self._preview:
            # The one place a tab can carry this: `Adw.TabPage` has no italic
            # and no markup, and the indicator slot holds the plan's mark. A
            # preview is unedited by definition — editing promotes it — so the
            # git mark it would otherwise show is the least useful thing here.
            tab.set_icon(Gio.ThemedIcon.new(PREVIEW_ICON))
            tab.set_tooltip(f"{tab_marks.tooltip(str(page.path), status)}\n{PREVIEW_NOTE}")
        elif self.setting("tabs.indicators.vcs", "icon") == "icon":
            _set_icon(tab.set_icon, tab_marks.vcs_icon(status))
        else:
            _set_icon(tab.set_icon, None)
        impact = self.setting("tabs.indicators.plan_impact", "icon") == "icon"
        _set_icon(tab.set_indicator_icon, tab_marks.impact_icon(status) if impact else None)

    def _name_for(self, page: Page) -> str:
        """Enough of the path to tell two tabs apart.

        Every Terraform module has a `main.tf`, so three tabs reading `main.tf`
        is the ordinary case rather than the unlucky one.
        """
        name = page.path.name
        clashes = [other for other in self.pages.values() if other.path.name == name]
        if len(clashes) < 2:
            return name
        return f"{page.path.parent.name}/{name}"

    def every_page(self) -> list[Page]:
        """Every file open, in tab order. `pages` is their paths."""
        found = []
        for index in range(self._tabs.get_n_pages()):
            page = getattr(self._tabs.get_nth_page(index), "page", None)
            if page is not None:
                found.append(page)
        return found

    def _retitle_all(self) -> None:
        for index in range(self._tabs.get_n_pages()):
            tab = self._tabs.get_nth_page(index)
            page = getattr(tab, "page", None)
            if page is not None:
                self._retitle(tab, page)

    def _new_tab(self, child: Gtk.Widget) -> Adw.TabPage:
        """Beside the tab you are on, or at the end of the row."""
        selected = self._tabs.get_selected_page()
        if self.setting("tabs.new_tab_position", "after_current") == "end" or selected is None:
            return self._tabs.append(child)
        return self._tabs.insert(child, self._tabs.get_page_position(selected) + 1)

    def _on_middle_click(self, gesture, _presses: int, x: float, y: float) -> None:
        """Closes whichever tab the pointer is over, and nothing when over none."""
        if not self.setting("tabs.middle_click_closes", True):
            return
        tab = _tab_under(self._tab_bar, self._tabs, x, y)
        if tab is None:
            return
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self._tabs.close_page(tab)

    def put_above_the_files(self, widget: Gtk.Widget) -> None:
        """Adds a bar below the tabs and above the file.

        The find row belongs over the file it is searching, not over the tab
        strip — a row above the tabs looks like it applies to all of them.
        """
        self._layout.add_top_bar(widget)

    def _apply_view_state(self, page) -> None:
        """A file opened after a toggle gets the same treatment as the rest."""
        if self._view_state.get("wrapped"):
            page.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        if self._view_state.get("ruler"):
            page.view.set_show_right_margin(True)
        page.hovers_shown = self._view_state.get("hovers", True)

    def set_wrapped(self, wrapped: bool) -> None:
        for page in self.pages.values():
            page.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR if wrapped else Gtk.WrapMode.NONE)
        self._view_state["wrapped"] = wrapped

    def set_ruler_shown(self, shown: bool) -> None:
        for page in self.pages.values():
            page.view.set_show_right_margin(shown)
        self._view_state["ruler"] = shown

    def set_hovers_shown(self, shown: bool) -> None:
        """Turns the hover popups off. Every layer toggles on its own."""
        self._view_state["hovers"] = shown
        for page in self.pages.values():
            page.hovers_shown = shown

    def _touch(self, page) -> None:
        """Records that this file was just looked at, for sorting by recency."""
        self._touches += 1
        self._touched[page.path] = self._touches

    @property
    def preview(self) -> Path | None:
        """Which tab is the preview, if any."""
        return self._preview

    def promote(self, path: Path | None = None) -> None:
        """Makes the preview permanent.

        Editing it is what promotes it — the `promote_preview_on` setting. The
        moment somebody types into a file they are no longer browsing, and a
        tab that vanished under an edit would be the worst kind of surprise.
        """
        wanted = Path(path).resolve() if path is not None else self._preview
        if wanted is None or wanted != self._preview:
            return
        self._preview = None
        page = self.pages.get(wanted)
        if page is not None:
            # Retitled after clearing it, so the mark goes with the state.
            self._retitle(self._page_for(page), page)

    def reopen_last_closed(self) -> Path | None:
        """The most recently closed file, so closing one by accident is cheap."""
        while self._closed:
            path = self._closed.pop()
            if path not in self.pages:
                return path
        return None

    def close_gone(self) -> None:
        """Tabs whose file is no longer on disk. An unsaved one is kept."""
        for page, tab in list(self._each()):
            if not page.path.exists() and not page.modified:
                self._tabs.close_page(tab)

    def close_untouched(self, touched: set[Path]) -> None:
        """Its version of "close unmodified", for infrastructure.

        Files the plan does not touch, so what is left is what the change is
        about. Anything unsaved stays: closing an edit nobody has saved is not
        a tidy-up.
        """
        wanted = {Path(path).resolve() for path in touched}
        for page, tab in list(self._each()):
            if page.path.resolve() not in wanted and not page.modified:
                self._tabs.close_page(tab)

    def pin_current(self) -> bool:
        """Pins or unpins the tab in front, and says which it now is."""
        tab = self._tabs.get_selected_page()
        if tab is None:
            return False
        # Pinning belongs to the view, not the page: `Adw.TabPage` has
        # `get_pinned` and no setter at all.
        self._tabs.set_page_pinned(tab, not tab.get_pinned())
        return tab.get_pinned()

    def sort_tabs(self, by: str, statuses: dict | None = None) -> list[Path]:
        """Reorders the tabs and returns the order they are now in.

        "Manual" is not a sort — it is the absence of one, so it leaves the
        tabs exactly where they are rather than pretending to do something.
        """
        if by == "manual":
            return [page.path for page, _tab in self._each()]

        pages = [(page, tab) for page, tab in self._each()]
        keys = {
            "name": lambda page: (page.path.name.lower(), str(page.path)),
            "path": lambda page: str(page.path).lower(),
            "recent": lambda page: -self._touched.get(page.path, 0),
            "plan-impact": lambda page: (
                -_impact_of(self._statuses.get(page.path.resolve())),
                page.path.name.lower(),
            ),
        }
        key = keys.get(by)
        if key is None:
            return [page.path for page, _tab in pages]
        for position, (_page, tab) in enumerate(sorted(pages, key=lambda pair: key(pair[0]))):
            self._tabs.reorder_page(tab, position)
        return [page.path for page, _tab in self._each()]

    def close_others(self) -> None:
        """Everything but the tab in front."""
        keep = self._tabs.get_selected_page()
        if keep is not None:
            self._tabs.close_other_pages(keep)

    def close_before(self) -> None:
        keep = self._tabs.get_selected_page()
        if keep is not None:
            self._tabs.close_pages_before(keep)

    def close_after(self) -> None:
        keep = self._tabs.get_selected_page()
        if keep is not None:
            self._tabs.close_pages_after(keep)

    def close_all(self) -> None:
        for tab in [self._tabs.get_nth_page(i) for i in range(self._tabs.get_n_pages())]:
            self._tabs.close_page(tab)

    def close_saved(self) -> None:
        """Everything with nothing unsaved in it. Leaves the rest alone."""
        for page, tab in list(self._each()):
            if not page.modified:
                self._tabs.close_page(tab)

    def _each(self):
        for index in range(self._tabs.get_n_pages()):
            tab = self._tabs.get_nth_page(index)
            for page in self.pages.values():
                if self._page_for(page) is tab:
                    yield page, tab
                    break

    def new_file(self) -> None:
        """Whatever the window does about a new file, when it has said so."""
        if self._on_new_file is not None:
            self._on_new_file()

    def _new_from_overview(self):
        """The overview's own new-tab button, answered by the same command.

        It has to hand a page back, and asking for a file is a dialog rather
        than something with an answer now — so the overview closes and the
        window asks, which is what pressing the other new-tab button does.
        """
        self._overview.set_open(False)
        self.new_file()
        tab = self._tabs.get_selected_page()
        return tab

    def show_every_tab(self) -> None:
        """The overview, which is the toolkit's own answer to twelve open files."""
        overview = getattr(self, "_overview", None)
        if overview is not None:
            overview.set_open(True)

    def next_tab(self) -> None:
        """The next open file, wrapping at the end."""
        pages = self._tabs.get_n_pages()
        if pages < 2:
            return
        here = self._tabs.get_page_position(self._tabs.get_selected_page())
        self._tabs.set_selected_page(self._tabs.get_nth_page((here + 1) % pages))

    def close_current(self) -> None:
        """Closes the tab in front. Does nothing when there is none."""
        tab = self._tabs.get_selected_page()
        if tab is not None:
            self._tabs.close_page(tab)

    def _page_for(self, page: Page) -> Adw.TabPage:
        for index in range(self._tabs.get_n_pages()):
            tab = self._tabs.get_nth_page(index)
            if getattr(tab, "page", None) is page:
                return tab
        raise LookupError(page.path)

    def _on_close(self, view: Adw.TabView, tab: Adw.TabPage) -> bool:
        """Asks before losing work, and closes at once when there is none.

        `Adw.TabView` lets the answer arrive later, so the dialog is put and the
        close finished in its response — no modal loop, and no tab that
        disappears while the question is still on screen.
        """
        page = getattr(tab, "page", None)
        if (
            page is None
            or not page.modified
            or not self.setting("tabs.confirm_close_unsaved", True)
        ):
            self._finish_close(view, tab, page)
            return True

        selection = Selection(
            tabs=(
                OpenTab(
                    path=page.path,
                    unsaved=True,
                    changed_lines=changed_lines(page.document.text, page.text()),
                ),
            ),
            scope=Scope.THIS,
        )

        def answered(answer: close_dialog.Answer) -> None:
            if answer in (close_dialog.Answer.CANCEL, close_dialog.Answer.KEEP_OPEN):
                view.close_page_finish(tab, False)
                return
            if answer is close_dialog.Answer.SAVE:
                page.save(
                    trim=bool(self.setting("editor.trim_trailing_whitespace_on_save", True)),
                    final_newline=bool(self.setting("editor.ensure_final_newline", True)),
                )
            self._finish_close(view, tab, page)

        root = self.get_root()
        if not isinstance(root, Gtk.Window):
            # No window to be modal against — never lose the file to that.
            view.close_page_finish(tab, False)
            return True
        close_dialog.ask(root, selection, answered)
        return True

    def _finish_close(self, view: Adw.TabView, tab: Adw.TabPage, page) -> None:
        if page is not None:
            self.pages.pop(page.path, None)
            self._closed.append(page.path)
            if self._preview == page.path:
                self._preview = None
        view.close_page_finish(tab, True)
        self._retitle_all()
        if not self.pages and self._on_empty is not None:
            self._on_empty()


def apply_display(view: GtkSource.View, *, indentation, settings=None) -> None:
    """The display row, in one place so no widget decides it alone.

    It took a `settings` argument from the start and every caller passed None,
    so line wrap, whitespace and the ruler were settings nothing could turn on.
    """
    get = settings.get if settings is not None else (lambda _k, default=None: default)

    view.set_show_line_numbers(bool(get("editor.show_line_numbers", True)))
    view.set_highlight_current_line(True)
    view.set_auto_indent(True)
    view.set_indent_on_tab(True)
    view.set_smart_backspace(True)
    view.set_tab_width(indentation.width)
    view.set_indent_width(indentation.width)
    view.set_insert_spaces_instead_of_tabs(not indentation.uses_tabs)
    view.set_show_right_margin(bool(get("editor.rulers", False)))
    view.set_right_margin_position(int(get("editor.wrap_column", 100)))
    view.set_wrap_mode(
        Gtk.WrapMode.WORD_CHAR if get("editor.word_wrap", False) else Gtk.WrapMode.NONE
    )

    buffer = view.get_buffer()
    buffer.set_highlight_matching_brackets(True)

    # Whitespace and invisibles, off until asked for — and **leading and
    # trailing only**. Dots inside a string change what the string looks like,
    # which in a language where a string is often a policy document is the one
    # place they must not appear.
    drawer = view.get_space_drawer()
    drawer.set_types_for_locations(
        GtkSource.SpaceLocationFlags.LEADING | GtkSource.SpaceLocationFlags.TRAILING,
        GtkSource.SpaceTypeFlags.SPACE | GtkSource.SpaceTypeFlags.TAB,
    )
    drawer.set_types_for_locations(
        GtkSource.SpaceLocationFlags.INSIDE_TEXT, GtkSource.SpaceTypeFlags.NONE
    )
    drawer.set_enable_matrix(bool(get("editor.show_whitespace", False)))


def _set_icon(setter, name: str | None) -> None:
    setter(Gio.ThemedIcon.new(name) if name else None)


def _scrolled(child: Gtk.Widget) -> Gtk.ScrolledWindow:
    scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
    scroller.set_child(child)
    return scroller


def _relative(path: Path, workspace: Path | None) -> Path:
    """How the engine names a file: relative to the workspace it ran in."""
    if workspace is None:
        return Path(path.name)
    try:
        return path.resolve().relative_to(Path(workspace).resolve())
    except ValueError:
        return Path(path.name)


def _tab_widgets(bar: Adw.TabBar) -> list[Gtk.Widget]:
    """The bar's per-tab widgets, in the order the tabs are in.

    `Adw.TabBar` offers no hit-test and `Adw.TabPage` is not a widget, so the
    only route to "which tab is at this x" is the bar's own children. They are
    unnamed gizmos carrying nothing that identifies a page — see finding 006.
    """
    found: list[Gtk.Widget] = []

    def walk(widget: Gtk.Widget) -> None:
        if type(widget).__name__ == "AdwTabBox" and widget.get_width() > 0:
            child = widget.get_first_child()
            while child is not None:
                if type(child).__name__ == "AdwGizmo":
                    found.append(child)
                child = child.get_next_sibling()
            return
        child = widget.get_first_child()
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(bar)
    return found


def _tab_under(bar: Adw.TabBar, tabs: Adw.TabView, x: float, y: float):
    """The page at this point in the bar, or None when the mapping is not safe.

    The position of a gizmo among its siblings is the position of its page.
    That is libadwaita's internal layout, so it is checked rather than trusted:
    a count that disagrees means the layout changed, and middle-click does
    nothing. A dead shortcut is survivable; closing the wrong file is not.
    """
    widgets = _tab_widgets(bar)
    if len(widgets) != tabs.get_n_pages():
        return None
    for index, widget in enumerate(widgets):
        point = bar.compute_point(widget, Graphene.Point().init(x, y))
        if point is None:
            continue
        found, local = point
        if not found:
            continue
        if 0 <= local.x <= widget.get_width() and 0 <= local.y <= widget.get_height():
            return tabs.get_nth_page(index)
    return None


def _impact_of(status) -> int:
    """How much the plan does to a file, most consequential first."""
    if status is None:
        return -1
    return {"destroy": 4, "replace": 3, "change": 2, "create": 1, "untouched": 0}.get(
        getattr(getattr(status, "impact", None), "value", ""), 0
    )
