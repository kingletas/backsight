"""The library: everything reusable, searchable, one keystroke from the buffer.

The complaint this answers is writing the same block for the twentieth time in
an editor that is supposed to know Terraform. So the shortest path matters more
than the browsing: type a word, see what matches, press Return, it is in the
file with the first field selected.

A runbook is the one that is read rather than inserted, so it opens its steps
instead — each with the block or the command it needs, and each insertable on
its own. A procedure is a list of things to do, and the useful thing is doing
one of them.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.engine.library.entry import Entry, Kind
from backsight.engine.library.placeholders import resolve
from backsight.engine.library.store import Library

NOTHING_YET = "Nothing here yet. Select a block in a file and choose Save to library."
NOTHING_MATCHED = "Nothing matches that"

# Enough to choose from, few enough to read. Past this, type another word.
MOST = 40

# About five rows. Enough that the list is something you look down.
ROWS_SHOWN = 190

# The preview is confirmation, not reading — the file is where you read it.
PREVIEW_TALL = 150


class LibraryPanel(Adw.Bin):
    """Search, what matched, and what the one in front of you actually says."""

    def __init__(
        self,
        *,
        on_insert: Callable[[Entry], None] | None = None,
        on_open: Callable[[Entry], None] | None = None,
        on_edit: Callable[[Entry], None] | None = None,
        on_run: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._on_insert = on_insert
        self._on_open = on_open
        self._on_edit = on_edit
        self._on_run = on_run
        self._library = Library()
        self._showing: list[Entry] = []
        self._chosen: Entry | None = None
        self._generate: Callable[[str], list[Entry]] | None = None

        self.search = Gtk.SearchEntry(placeholder_text="bucket, rds, rotate…")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", lambda *_: self._redraw())
        self.search.connect("activate", lambda *_: self._take_the_first())

        self._kinds = Gtk.DropDown.new_from_strings(["Everything", *[kind.label for kind in Kind]])
        self._kinds.connect("notify::selected", lambda *_: self._redraw())

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        top.append(self.search)
        top.append(self._kinds)

        self._list = Gtk.ListBox()
        self._list.add_css_class("tf-tree")
        self._list.connect("row-selected", self._chose)
        self._list.connect("row-activated", lambda _l, row: self._use(getattr(row, "entry", None)))

        # Room for several at once. A list that shows two rows is a list you
        # scroll rather than one you choose from, and choosing is the point.
        listed = Gtk.ScrolledWindow(vexpand=True)
        listed.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        listed.set_min_content_height(ROWS_SHOWN)
        listed.set_child(self._list)

        self._said = Gtk.Label(label=NOTHING_YET, xalign=0.0, wrap=True)
        self._said.add_css_class("tf-small")
        self._said.add_css_class("tf-faint")

        self._preview = Gtk.Label(xalign=0.0, yalign=0.0, selectable=True)
        self._preview.add_css_class("tf-mono")
        self._preview.add_css_class("tf-small")
        shown = Gtk.ScrolledWindow()
        shown.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        shown.set_propagate_natural_height(True)
        shown.set_max_content_height(PREVIEW_TALL)
        shown.set_child(self._preview)
        self._preview_holder = shown

        self._steps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._steps.set_visible(False)

        self._use_it = Gtk.Button(label="Insert")
        self._use_it.add_css_class("tf-primary")
        self._use_it.set_halign(Gtk.Align.START)
        self._use_it.set_sensitive(False)
        self._use_it.connect("clicked", lambda *_: self._use(self._chosen))

        self._edit = Gtk.Button(label="Edit")
        self._edit.add_css_class("tf-quiet")
        self._edit.set_visible(False)
        self._edit.connect(
            "clicked", lambda *_: self._on_edit(self._chosen) if self._on_edit else None
        )

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons.append(self._use_it)
        buttons.append(self._edit)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(10 if edge in ("top", "bottom") else 12)
        box.append(top)
        box.append(self._said)
        box.append(listed)
        box.append(shown)
        box.append(self._steps)
        box.append(buttons)
        self.set_child(box)

    def show(self, library: Library) -> None:
        self._library = library
        self._redraw()

    @property
    def showing(self) -> list[Entry]:
        return list(self._showing)

    @property
    def chosen(self) -> Entry | None:
        return self._chosen

    @property
    def said(self) -> str:
        return self._said.get_text()

    def look_for(self, term: str) -> None:
        """What the palette and the context menu do — search from elsewhere."""
        self.search.set_text(term)
        self._redraw()

    def _wanted_kind(self) -> Kind | None:
        chosen = self._kinds.get_selected()
        return None if chosen <= 0 else list(Kind)[chosen - 1]

    def ask_the_schema(self, generate: Callable[[str], list[Entry]] | None) -> None:
        """Where the entries generated from the provider schema come from.

        Asked at search time rather than loaded: a provider index holds
        thousands of resource types, and building two entries for every one of
        them to show a list of ten is work nobody asked for.
        """
        self._generate = generate

    def _redraw(self) -> None:
        while (row := self._list.get_first_child()) is not None:
            self._list.remove(row)
        term = self.search.get_text()
        found = self._library.search(term, kind=self._wanted_kind())
        found.extend(self._from_the_schema(term, found))
        self._showing = found[:MOST]
        for entry in self._showing:
            self._list.append(_row(entry))
        if not self._library.entries:
            self._said.set_text(NOTHING_YET)
        elif not found:
            self._said.set_text(NOTHING_MATCHED)
        else:
            more = len(found) - len(self._showing)
            self._said.set_text(
                f"{len(found)} of {len(self._library)}"
                + (f" · showing {len(self._showing)}" if more else "")
            )
        self._said.set_visible(True)
        self._choose(None)

    def _from_the_schema(self, term: str, already: list[Entry]) -> list[Entry]:
        """Generated entries for what was typed, minus anything hand-written.

        Nothing until somebody types: a list of every resource type in AWS is
        not a library, it is a directory listing.
        """
        wanted = term.strip()
        if (
            self._generate is None
            or len(wanted) < 3
            or self._wanted_kind() not in (None, Kind.SNIPPET)
        ):
            return []
        taken = {entry.name for entry in already}
        return [entry for entry in self._generate(wanted) if entry.name not in taken]

    def _chose(self, _list, row) -> None:
        self._choose(getattr(row, "entry", None))

    def _choose(self, entry: Entry | None) -> None:
        self._chosen = entry
        self._use_it.set_sensitive(entry is not None)
        self._edit.set_visible(entry is not None and entry.source.is_editable)
        self._draw_steps(entry)
        if entry is None:
            self._preview.set_text("")
            self._preview_holder.set_visible(False)
            return
        self._use_it.set_label(entry.kind.what_it_does)
        self._preview.set_text(resolve(entry.body).text.rstrip())
        self._preview_holder.set_visible(bool(entry.body.strip()))

    def _draw_steps(self, entry: Entry | None) -> None:
        while (child := self._steps.get_first_child()) is not None:
            self._steps.remove(child)
        if entry is None or not entry.steps:
            self._steps.set_visible(False)
            return
        for number, step in enumerate(entry.steps, start=1):
            self._steps.append(self._step(number, step))
        self._steps.set_visible(True)

    def _step(self, number: int, step) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=f"{number}. {step.title}", xalign=0.0, wrap=True)
        title.add_css_class("tf-medium")
        title.add_css_class("tf-small")
        box.append(title)
        if step.body.strip():
            said = Gtk.Label(label=step.body.strip(), xalign=0.0, wrap=True)
            said.add_css_class("tf-small")
            said.add_css_class("tf-faint")
            box.append(said)
            put_it_in = Gtk.Button(label="Insert this block")
            put_it_in.add_css_class("tf-quiet")
            put_it_in.set_halign(Gtk.Align.START)
            put_it_in.connect(
                "clicked",
                lambda *_a, text=step.body: (
                    self._on_insert(Entry(name=step.title, body=text)) if self._on_insert else None
                ),
            )
            box.append(put_it_in)
        if step.is_a_command:
            run = Gtk.Button(label=step.command)
            run.add_css_class("tf-quiet")
            run.add_css_class("tf-mono")
            run.set_halign(Gtk.Align.START)
            run.set_tooltip_text("Run this")
            run.connect(
                "clicked",
                lambda *_a, said=step.command: self._on_run(said) if self._on_run else None,
            )
            box.append(run)
        return box

    def _take_the_first(self) -> None:
        """Return in the search box uses the best match, without a click."""
        if self._showing:
            self._use(self._showing[0])

    def _use(self, entry: Entry | None) -> None:
        if entry is None:
            return
        if entry.kind in (Kind.EXAMPLE, Kind.RUNBOOK):
            if self._on_open is not None:
                self._on_open(entry)
            return
        if self._on_insert is not None:
            self._on_insert(entry)


def _row(entry: Entry) -> Gtk.ListBoxRow:
    row = Gtk.ListBoxRow()
    name = Gtk.Label(label=entry.name, xalign=0.0, hexpand=True)
    name.set_ellipsize(3)
    where = Gtk.Label(label=f"{entry.kind.label} · {entry.source.value}", xalign=1.0)
    where.add_css_class("tf-micro")
    where.add_css_class("tf-faint")
    line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    line.append(name)
    line.append(where)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    box.append(line)
    if entry.about:
        about = Gtk.Label(label=entry.about, xalign=0.0, wrap=True)
        about.add_css_class("tf-micro")
        about.add_css_class("tf-faint")
        box.append(about)
    row.set_child(box)
    row.entry = entry
    row.set_tooltip_text(entry.about or entry.name)
    return row
