"""The command palette: one entry, one list, six prefixes.

It is one of the two surfaces that cannot be hidden, because it is how
everything else is reached when the chrome is gone — so it never opens empty,
and Escape always closes it.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.app.dismissable import escape_closes, remembers_focus
from backsight.engine.presentation.palette import SUGGESTED, Entry, Results, results

PLACEHOLDER = "Type to search files"

# What each prefix is for, **as chips above the list with the one in play lit**.
# It was a grey line at the bottom, which is where a reader looks last and where
# a hint about how to use the thing they are already using is least use. Lighting
# the one in play is what makes it a control rather than a caption.
PREFIXES = (
    ("", "files"),
    ("@", "resources"),
    (":", "line"),
    ("#", "documentation"),
    (">", "commands"),
    ("!", "problems"),
)


class Palette(Adw.Window):
    """The palette, over whatever it was opened from."""

    def __init__(
        self,
        entries: list[Entry],
        suggestions: list[Entry],
        *,
        parent: Gtk.Window | None = None,
        on_choose: Callable[[Entry], None] | None = None,
    ) -> None:
        # A fixed height, because a palette that resizes on every keystroke is
        # a moving target. The list scrolls inside it.
        super().__init__(transient_for=parent, modal=True, default_width=560, default_height=420)
        self.set_title("Go to anything")
        self._entries = entries
        self._suggestions = suggestions
        self._on_choose = on_choose
        self._shown: list[Entry] = []
        self._by_row: dict[int, Entry] = {}
        self._next_row = 0

        self._entry = Gtk.SearchEntry(placeholder_text=PLACEHOLDER)
        # `changed`, not `search-changed`: the latter is debounced by about
        # 150ms, and matching here is over a list already in memory. Waiting
        # buys nothing and makes every keystroke feel late.
        self._entry.connect("changed", lambda *_: self.refresh())
        self._entry.connect("activate", lambda *_: self.choose())

        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self._list.add_css_class("tf-palette")
        self._list.connect("row-activated", lambda _l, row: self.choose(row.get_index()))

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_child(self._list)

        # Pressing one puts its prefix in the entry, so the chips teach the
        # keystroke rather than only naming it.
        self._chips: dict[str, Gtk.Widget] = {}
        legend = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for mark, what in PREFIXES:
            chip = Gtk.Button(label=f"{mark} {what}".strip())
            chip.add_css_class("tf-chip")
            chip.add_css_class("flat")
            chip.connect("clicked", lambda _b, m=mark: self._use(m))
            legend.append(chip)
            self._chips[mark] = chip

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(10)
        box.append(self._entry)
        box.append(legend)
        box.append(scroller)
        self.set_content(box)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        # **Escape, before the search field can eat it.** This window listened
        # for Escape from the day it was written and Escape did nothing, because
        # `Gtk.SearchEntry` installs its own Escape shortcut and stops the
        # event — so the controller above never saw it.
        escape_closes(self)
        remembers_focus(self, parent)

        self.refresh()

    def _use(self, mark: str) -> None:
        """Puts a prefix in the entry, keeping whatever was already typed."""
        said = self._entry.get_text().lstrip()
        for prefix, _what in PREFIXES:
            if prefix and said.startswith(prefix):
                said = said[len(prefix) :]
                break
        self._entry.set_text(f"{mark}{said.lstrip()}")
        self._entry.grab_focus()
        self._entry.set_position(-1)

    def _light_the_chip(self, raw: str) -> None:
        """Marks which prefix is in play. Exactly one, always."""
        said = raw.lstrip()
        found = next((mark for mark, _w in PREFIXES if mark and said.startswith(mark)), "")
        for mark, chip in self._chips.items():
            if mark == found:
                chip.add_css_class("tf-info")
            else:
                chip.remove_css_class("tf-info")

    @property
    def entry(self) -> Gtk.SearchEntry:
        return self._entry

    @property
    def shown(self) -> list[Entry]:
        """What is on screen now, matches then suggestions."""
        return list(self._shown)

    def refresh(self) -> None:
        said = self._entry.get_text()
        self._light_the_chip(said)
        found = results(self._entries, self._suggestions, said)
        self._draw(found)

    def choose(self, index: int | None = None) -> None:
        """Acts on the highlighted row, or on the first when none is."""
        if not self._shown:
            return
        if index is None:
            row = self._list.get_selected_row()
            index = row.get_index() if row is not None else next(iter(self._by_row), 0)
        chosen = self._row_entry(index)
        if chosen is None:
            return
        self.close()
        if self._on_choose is not None:
            self._on_choose(chosen)

    def _row_entry(self, index: int) -> Entry | None:
        """Which entry a row is.

        Row positions count the headings and `shown` does not, so the two are
        related by an explicit map rather than by arithmetic that would go
        wrong the moment a heading is added or removed.
        """
        return self._by_row.get(index)

    def _draw(self, found: Results) -> None:
        while (row := self._list.get_first_child()) is not None:
            self._list.remove(row)
        self._shown = []
        self._by_row = {}
        self._next_row = 0

        if found.matches:
            self._heading(found.heading)
            for entry in found.matches:
                self._row(entry)
        if found.suggestions:
            self._heading(SUGGESTED)
            for entry in found.suggestions:
                self._row(entry)
        if not self._shown:
            # Only reachable for a line query that is not a number. Saying so
            # beats an empty box that looks broken.
            self._heading("Nothing matches that")
        # The first row is a heading, which is not selectable. Select the
        # first real entry so Enter acts on the best match.
        first = next(iter(self._by_row), None)
        if first is not None:
            self._list.select_row(self._list.get_row_at_index(first))

    def _heading(self, text: str) -> None:
        label = Gtk.Label(label=text, xalign=0.0)
        label.add_css_class("tf-palette-heading")
        row = Gtk.ListBoxRow(child=label, selectable=False, activatable=False)
        self._list.append(row)
        self._next_row += 1

    def _row(self, entry: Entry) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        label = Gtk.Label(label=entry.label, xalign=0.0, hexpand=True)
        box.append(label)
        if entry.detail:
            detail = Gtk.Label(label=entry.detail, xalign=1.0)
            detail.add_css_class("tf-small")
            detail.add_css_class("tf-faint")
            box.append(detail)
        self._list.append(Gtk.ListBoxRow(child=box))
        self._by_row[self._next_row] = entry
        self._next_row += 1
        self._shown.append(entry)

    def _on_key(self, _controller, keyval: int, _code: int, _state) -> bool:
        """Everything but Escape, which `escape_closes` takes at capture."""
        return False
