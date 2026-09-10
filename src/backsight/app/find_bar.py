"""The find row, over the file it is searching.

Incremental, with the match count visible while typing, because a
search that says nothing about how many it found leaves you pressing Enter to
find out.

Replace-all **says how many it will change before it changes them**. "Replace
all" with no number is a decision made blind, and it is not undoable in one
step across a large file.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk

from backsight.app.find import Query, Search

SCANNING = "counting…"
NOTHING = "no matches"


def summary(count: int) -> str:
    """What the row says about how many were found."""
    if count < 0:
        return SCANNING
    if count == 0:
        return NOTHING
    return f"{count} match{'es' if count != 1 else ''}"


class FindBar(Adw.Bin):
    """One row: what to find, what to replace it with, and how many there are."""

    def __init__(self, on_close: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._search: Search | None = None
        self._on_close = on_close

        self._term = Gtk.SearchEntry(placeholder_text="Find", hexpand=True)
        self._term.connect("changed", lambda *_: self.refresh())
        self._term.connect("activate", lambda *_: self.next())

        self._replacement = Gtk.Entry(placeholder_text="Replace with", hexpand=True)

        self._count = Gtk.Label(xalign=1.0)
        self._count.add_css_class("tf-small")
        self._count.add_css_class("tf-faint")

        self._regex = Gtk.ToggleButton(label=".*", tooltip_text="Regular expression")
        self._case = Gtk.ToggleButton(label="Aa", tooltip_text="Match case")
        self._word = Gtk.ToggleButton(label="ab|", tooltip_text="Whole word")
        for toggle in (self._regex, self._case, self._word):
            toggle.add_css_class("flat")
            toggle.connect("toggled", lambda *_: self.refresh())

        find_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        find_row.append(self._term)
        find_row.append(self._count)
        for toggle in (self._regex, self._case, self._word):
            find_row.append(toggle)
        find_row.append(_button("go-up-symbolic", "Previous", self.previous))
        find_row.append(_button("go-down-symbolic", "Next", self.next))
        find_row.append(_button("window-close-symbolic", "Close", self.close))

        self._replace_all = Gtk.Button(label="Replace all")
        self._replace_all.connect("clicked", lambda *_: self.replace_all())

        replace_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        replace_row.append(self._replacement)
        replace_row.append(self._replace_all)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.add_css_class("tf-find")
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(8)
        box.append(find_row)
        box.append(replace_row)
        self.set_child(box)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        self.refresh()

    @property
    def term(self) -> Gtk.SearchEntry:
        return self._term

    @property
    def replacement(self) -> Gtk.Entry:
        return self._replacement

    @property
    def count(self) -> str:
        return self._count.get_label()

    def search_in(self, search: Search | None) -> None:
        """Points the row at a file's search, or at nothing."""
        self._search = search
        if search is not None:
            search.on_count(self._counted)
        self.refresh()

    def _counted(self, found: int) -> None:
        """The scan finished, or revised itself. Only the current file's count."""
        if self._search is None or not self._term.get_text():
            return
        self._count.set_text(summary(found))
        self._replace_all.set_sensitive(found > 0)

    def query(self) -> Query:
        return Query(
            text=self._term.get_text(),
            regex=self._regex.get_active(),
            case_sensitive=self._case.get_active(),
            whole_word=self._word.get_active(),
        )

    def refresh(self) -> None:
        """Re-runs the search as it is typed and reports what it found."""
        if self._search is None:
            self._count.set_text("")
            self._replace_all.set_sensitive(False)
            return
        self._search.look_for(self.query())
        found = self._search.count
        self._count.set_text(summary(found) if self._term.get_text() else "")
        # Nothing to replace is not an error, and a live button that does
        # nothing is worse than a dead one.
        self._replace_all.set_sensitive(found > 0)

    def next(self) -> None:
        if self._search is not None:
            self._search.next()

    def previous(self) -> None:
        if self._search is not None:
            self._search.previous()

    def replace_all(self) -> int:
        """Replaces every match and says how many that was."""
        if self._search is None:
            return 0
        changed = self._search.replace_all(self._replacement.get_text())
        self._count.set_text(f"{changed} replaced")
        return changed

    def close(self) -> None:
        if self._search is not None:
            self._search.clear()
        if self._on_close is not None:
            self._on_close()

    def _on_key(self, _controller, keyval: int, _code: int, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False


def _button(icon: str, tip: str, run: Callable[[], None]) -> Gtk.Button:
    button = Gtk.Button(icon_name=icon, tooltip_text=tip)
    button.add_css_class("flat")
    button.connect("clicked", lambda *_: run())
    return button
