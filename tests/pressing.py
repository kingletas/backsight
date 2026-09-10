"""Sending a real key press into a window, the way the display would.

**One helper, because the defect this exists for was about who sees the key
first.** `Gtk.Widget.activate_action` and calling a handler directly both skip
exactly that part: the palette's Escape handler was correct, connected and never
reached, because `Gtk.SearchEntry` installs its own Escape shortcut and stops
the event before a controller on the window can run. A test that calls the
handler passes against a window nobody can get out of.
"""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gtk  # noqa: E402

ESCAPE_HARDWARE_KEYCODE = 9


def press_escape(window: Gtk.Window) -> None:
    """Walks the toolkit's own controller chain, at every phase, in order."""
    for phase in (
        Gtk.PropagationPhase.CAPTURE,
        Gtk.PropagationPhase.TARGET,
        Gtk.PropagationPhase.BUBBLE,
    ):
        outward = phase is Gtk.PropagationPhase.BUBBLE
        chain = from_the_focus_up(window) if outward else from_the_window_down(window)
        for widget in chain:
            for controller in key_controllers(widget):
                if controller.get_propagation_phase() != phase:
                    continue
                if controller.emit("key-pressed", Gdk.KEY_Escape, ESCAPE_HARDWARE_KEYCODE, 0):
                    return


def key_controllers(widget: Gtk.Widget) -> list[Gtk.EventControllerKey]:
    found = []
    listed = widget.observe_controllers()
    for at in range(listed.get_n_items()):
        one = listed.get_item(at)
        if isinstance(one, Gtk.EventControllerKey):
            found.append(one)
    return found


def from_the_window_down(window: Gtk.Window) -> list[Gtk.Widget]:
    """The window, then each ancestor of the focus, ending at the focus."""
    return list(reversed(from_the_focus_up(window)))


def from_the_focus_up(window: Gtk.Window) -> list[Gtk.Widget]:
    found: list[Gtk.Widget] = []
    widget = window.get_focus() or window
    while widget is not None:
        found.append(widget)
        if widget is window:
            break
        widget = widget.get_parent()
    if window not in found:
        found.append(window)
    return found
