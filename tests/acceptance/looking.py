"""Asking a real window what it actually shows.

Two things a unit test never checks: that a widget is visible, and that it
has a size. A widget can be visible, hold the right text, pass every
assertion about its state, and be zero pixels wide. That is what happened.
"""

from __future__ import annotations

import time


def settle(_window=None, seconds: float = 0.6) -> None:
    """Runs the main loop until the layout has caught up."""
    from gi.repository import GLib

    context = GLib.MainContext.default()
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        if not context.iteration(False):
            time.sleep(0.005)


def drawn(widget) -> bool:
    """Whether this is actually on screen with room to be seen.

    Visible is not enough. A widget can be visible, hold the right text, and be
    zero pixels wide — which is exactly how the editor disappeared while every
    test about it passed.
    """
    return bool(widget.get_visible() and widget.get_width() > 0 and widget.get_height() > 0)


def labels(widget, found=None) -> list[str]:
    """Every piece of text on screen under this widget."""
    from gi.repository import Gtk

    found = [] if found is None else found
    if isinstance(widget, Gtk.Label):
        found.append(widget.get_text())
    child = widget.get_first_child()
    while child is not None:
        labels(child, found)
        child = child.get_next_sibling()
    return found


def says(widget, needle: str) -> bool:
    return any(needle in said for said in labels(widget))
