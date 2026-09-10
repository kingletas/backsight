"""The workspace switcher: where you are, and how to be somewhere else.

It replaces the "Open workspace" button, which was the window's primary action
for the few seconds before a workspace was open and a large accent-filled
control for the rest of the application's life.

**It is not an accent-filled button.** It is a quiet bordered control, because
it says where you are rather than asking you to do anything.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk

from backsight.app.workspaces import Known

NOTHING_OPEN = "No workspace"
HEADING = "Open workspaces"
OPEN_ANOTHER = "Open workspace…"
THE_EXAMPLE = "Open example workspace"

# `prod` is the only environment that gets a chip. An uncoloured name is the
# neutral case, and inventing a colour for `staging` would say something about
# it that is not true.
CHIPPED = {"prod": "tf-disruptive"}


class WorkspaceSwitcher(Gtk.MenuButton):
    """The window's title widget."""

    def __init__(
        self,
        *,
        on_open: Callable[[Path], None] | None = None,
        on_browse: Callable[[], None] | None = None,
        on_example: Callable[[], None] | None = None,
        accelerator: str = "Ctrl+O",
    ) -> None:
        super().__init__()
        self._on_open = on_open
        self._on_browse = on_browse
        self._on_example = on_example
        self._accelerator = accelerator
        self._known: list[Known] = []
        self._current: Path | None = None

        self.add_css_class("tf-quiet")
        self.add_css_class("tf-workspace-switcher")

        self._name = Gtk.Label(label=NOTHING_OPEN)
        self._name.add_css_class("tf-medium")
        self._chip = Gtk.Label()
        self._chip.add_css_class("tf-chip")
        self._chip.set_visible(False)

        face = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        face.append(self._name)
        face.append(self._chip)
        face.append(Gtk.Image.new_from_icon_name("pan-down-symbolic"))
        self.set_child(face)

        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self._list.add_css_class("tf-tree")
        self._popover = Gtk.Popover()
        self._popover.set_child(self._list)
        self.set_popover(self._popover)
        self.show(None, [])

    @property
    def rows(self) -> list[str]:
        """Every row's first line, for anything checking what is offered."""
        found = []
        row = self._list.get_first_child()
        while row is not None:
            label = _first_label(row)
            if label is not None:
                found.append(label.get_label())
            row = row.get_next_sibling()
        return found

    def show(self, current: Known | None, known: list[Known]) -> None:
        """Draws the switcher and rebuilds its list."""
        self._current = current.path if current is not None else None
        self._known = list(known)

        self._name.set_label(current.name if current else NOTHING_OPEN)
        self._name.remove_css_class("tf-faint")
        if current is None:
            self._name.add_css_class("tf-faint")

        level = CHIPPED.get(current.environment if current else "", "")
        self._chip.set_visible(bool(level))
        if level:
            self._chip.set_label(current.environment)
            for old in ("tf-safe", "tf-disruptive", "tf-irreversible", "tf-info"):
                self._chip.remove_css_class(old)
            self._chip.add_css_class(level)

        self._rebuild()

    def _rebuild(self) -> None:
        while (row := self._list.get_first_child()) is not None:
            self._list.remove(row)

        if self._known:
            self._list.append(_heading(HEADING))
            for known in self._known:
                self._list.append(self._workspace_row(known))
            self._list.append(Gtk.Separator())

        self._list.append(
            _action_row(OPEN_ANOTHER, "folder-open-symbolic", self._accelerator, self._browse)
        )
        if not self._known and self._on_example is not None:
            # With nothing open this is the only place the example lives.
            self._list.append(
                _action_row(THE_EXAMPLE, "media-playback-start-symbolic", "", self._example)
            )

    def _workspace_row(self, known: Known) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(8 if edge in ("top", "bottom") else 11)

        line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name = Gtk.Label(label=known.name, xalign=0.0, hexpand=True)
        line.append(name)
        if known.path == self._current:
            line.append(Gtk.Image.new_from_icon_name("object-select-symbolic"))
        box.append(line)

        detail = Gtk.Label(label=known.summary(), xalign=0.0, wrap=True)
        detail.add_css_class("tf-micro")
        detail.add_css_class(known.state_class)
        box.append(detail)

        row = Gtk.ListBoxRow(child=box, activatable=known.exists)
        if known.path == self._current:
            row.add_css_class("tf-current")
        if known.exists:
            click = Gtk.GestureClick()
            click.connect("released", lambda *_a, p=known.path: self._choose(p))
            row.add_controller(click)
        return row

    def _choose(self, path: Path) -> None:
        self._popover.popdown()
        if self._on_open is not None and path != self._current:
            self._on_open(path)

    def _browse(self) -> None:
        self._popover.popdown()
        if self._on_browse is not None:
            self._on_browse()

    def _example(self) -> None:
        self._popover.popdown()
        if self._on_example is not None:
            self._on_example()


def _heading(text: str) -> Gtk.Widget:
    label = Gtk.Label(label=text, xalign=0.0)
    label.add_css_class("tf-micro")
    label.add_css_class("tf-faint")
    for edge in ("top", "bottom", "start", "end"):
        getattr(label, f"set_margin_{edge}")(7 if edge in ("top", "bottom") else 11)
    return Gtk.ListBoxRow(child=label, activatable=False, selectable=False)


def _action_row(text: str, icon: str, accelerator: str, run: Callable[[], None]) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
    for edge in ("top", "bottom", "start", "end"):
        getattr(box, f"set_margin_{edge}")(7 if edge in ("top", "bottom") else 11)
    box.append(Gtk.Image.new_from_icon_name(icon))
    box.append(Gtk.Label(label=text, xalign=0.0, hexpand=True))
    if accelerator:
        keys = Gtk.Label(label=accelerator)
        keys.add_css_class("tf-micro")
        keys.add_css_class("tf-faint")
        box.append(keys)

    row = Gtk.ListBoxRow(child=box)
    click = Gtk.GestureClick()
    click.connect("released", lambda *_a: run())
    row.add_controller(click)
    return row


def _first_label(widget) -> Gtk.Label | None:
    if isinstance(widget, Gtk.Label):
        return widget
    child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
    while child is not None:
        found = _first_label(child)
        if found is not None:
            return found
        child = child.get_next_sibling()
    return None
