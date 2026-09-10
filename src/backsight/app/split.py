"""Two editors side by side, and which one your typing goes to.

Three menu items have pointed at this since the menus were written. The reason
it was not built is that the window reaches into the editor from eighty-nine
places, and a second editor means every one of them deciding which it meant.

So none of them decides. The window holds a `Split`, and `active` is whichever
pane last had the keyboard — every call site follows the focus without knowing a
split exists. That keeps the change to this file and to the three actions,
instead of spreading it through the window.

A split is two panes, never a tree of them. Editors that let you split without
limit are editors people get lost in, and the second pane is for the one thing
splits are actually for: reading one file while changing another.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk


class Split(Adw.Bin):
    """One editor, or two, and the one the keyboard is in."""

    def __init__(self, build: Callable[[], object]) -> None:
        super().__init__()
        self._build = build
        self._paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        first = build()
        self._panes: list[object] = [first]
        self._active = first
        self._paned.set_start_child(first)
        self._paned.set_resize_start_child(True)
        self._paned.set_resize_end_child(True)
        self.set_child(self._paned)
        self._watch(first)

    @property
    def active(self):
        """The pane the keyboard is in. Every call site reads this."""
        return self._active

    @property
    def panes(self) -> list:
        return list(self._panes)

    @property
    def is_split(self) -> bool:
        return len(self._panes) > 1

    def split(self, orientation: Gtk.Orientation) -> object | None:
        """Opens a second pane, or turns the one that exists.

        Splitting again with a split already open changes its direction rather
        than making a third, so the command is never a dead key and never grows
        a tree nobody asked for.
        """
        if self.is_split:
            self._paned.set_orientation(orientation)
            return None
        second = self._build()
        self._panes.append(second)
        self._paned.set_orientation(orientation)
        self._paned.set_end_child(second)
        self._paned.set_position(max(1, self._span(orientation) // 2))
        self._watch(second)
        self._make_active(second)
        return second

    def _span(self, orientation: Gtk.Orientation) -> int:
        return self.get_width() if orientation is Gtk.Orientation.HORIZONTAL else self.get_height()

    def unsplit(self) -> None:
        """Back to one pane, keeping whichever one you were in."""
        if not self.is_split:
            return
        keeping = self._active
        going = next(pane for pane in self._panes if pane is not keeping)
        self._paned.set_start_child(None)
        self._paned.set_end_child(None)
        self._panes = [keeping]
        self._paned.set_start_child(keeping)
        self._active = keeping
        del going

    def other(self):
        """The pane you are not in, or None when there is only one."""
        return next((pane for pane in self._panes if pane is not self._active), None)

    def focus_other(self) -> None:
        found = self.other()
        if found is not None:
            self._make_active(found)
            found.grab_focus()

    def _watch(self, pane) -> None:
        """Whichever pane last took the keyboard becomes the active one."""
        controller = Gtk.EventControllerFocus()
        controller.connect("enter", lambda *_a, p=pane: self._make_active(p))
        pane.add_controller(controller)
        # A click lands before focus does on some widgets, and a pane you
        # clicked into is a pane you meant.
        click = Gtk.GestureClick()
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", lambda *_a, p=pane: self._make_active(p))
        pane.add_controller(click)

    def _make_active(self, pane) -> None:
        if pane not in self._panes:
            return
        self._active = pane
        for each in self._panes:
            each.remove_css_class("tf-pane-active")
        if self.is_split:
            pane.add_css_class("tf-pane-active")
