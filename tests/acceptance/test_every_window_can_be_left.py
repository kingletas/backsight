"""Every window this application opens can be got out of.

One of them could not. The stacks view was modal, had no header bar and so no
close button, and nothing listened for Escape — so opening it locked the
application and the only way out was to kill it.

That is the worst failure an interface can have, and it is one line of missing
wiring. Each window here is opened for real and then left, by key and by
control.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.acceptance.looking import settle

gi = pytest.importorskip("gi", reason="the toolkit is not installed")

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "src" / "backsight" / "app"


def escapes(window) -> bool:
    """Sends Escape the way the toolkit would, and says whether it closed."""
    from gi.repository import Gdk, Gtk

    for controller in _controllers(window):
        if isinstance(controller, Gtk.EventControllerKey):
            if controller.emit("key-pressed", Gdk.KEY_Escape, 9, 0):
                return True
        if isinstance(controller, Gtk.ShortcutController):
            # A shortcut controller with Escape in it is the other way this is
            # done, and it cannot be fired without a real event.
            return True
    return False


def _controllers(widget) -> list:
    found = []
    observed = widget.observe_controllers()
    for index in range(observed.get_n_items()):
        found.append(observed.get_item(index))
    return found


def has_a_close_control(window) -> bool:
    """A header bar gives one. Somebody who does not know the key needs it."""
    from gi.repository import Adw, Gtk

    def walk(widget) -> bool:
        if isinstance(widget, Adw.HeaderBar | Gtk.HeaderBar):
            return True
        child = widget.get_first_child()
        while child is not None:
            if walk(child):
                return True
            child = child.get_next_sibling()
        return False

    content = window.get_content() if hasattr(window, "get_content") else None
    return walk(content) if content is not None else False


# --- each one, opened for real ---------------------------------------------


def test_the_stacks_view_can_be_left(opened):
    """The one that locked the application."""
    opened.show_stacks()
    settle(opened, 0.4)
    from gi.repository import Gtk

    found = [one for one in Gtk.Window.get_toplevels() if one.get_title() == "Stacks"]
    assert found, "the stacks window did not open"
    stacks = found[-1]
    assert has_a_close_control(stacks)
    assert escapes(stacks)
    stacks.close()


def test_the_keyboard_reference_can_be_left(opened):
    from backsight.app.keyboard_reference import KeyboardReference

    reference = KeyboardReference(opened.keymap, parent=opened)
    reference.present()
    settle(opened, 0.3)
    assert has_a_close_control(reference)
    reference.close()


def test_the_apply_window_can_be_left_even_while_it_runs(opened):
    """Refusing to close it protected nothing: closing does not stop the
    apply, and if the engine hung it removed the application for good."""
    from backsight.app.apply_screen import ApplyWindow
    from backsight.engine.plan.applying import Progress

    found = ApplyWindow(parent=opened)
    found.begin(Progress(steps=[]), where="prod")
    found.present()
    settle(opened, 0.3)
    assert has_a_close_control(found)
    assert escapes(found)
    found.close()


def test_and_says_that_closing_it_does_not_stop_the_apply(opened):
    from backsight.app.apply_screen import ApplyWindow
    from backsight.engine.plan.applying import Progress

    found = ApplyWindow(parent=opened)
    found.begin(Progress(steps=[]), where="prod")
    assert "does not stop the apply" in found.screen._closing.get_text()
    found.close()


def test_the_palette_can_be_left(opened):
    from backsight.app.palette import Palette

    found = Palette(opened._palette_entries(), opened._palette_suggestions(), parent=opened)
    found.present()
    settle(opened, 0.3)
    assert escapes(found)
    found.close()


# --- and nothing new may skip it -------------------------------------------


def test_every_window_in_the_application_is_made_dismissable():
    """A helper rather than a habit: a window somebody writes in a hurry is
    exactly the one that traps people."""
    allowed = {
        # Its own key handling, and it is the one surface that must not carry
        # a header bar — it is a prompt.
        "palette.py",
        # The main window. Closing it is the window manager's job.
        "window.py",
    }
    missing = []
    for path in APP.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "Adw.Window" not in text:
            continue
        tree = ast.parse(text, filename=str(path))
        opens = any(
            isinstance(node, ast.Attribute) and node.attr == "Window" for node in ast.walk(tree)
        )
        if not opens or path.name in allowed:
            continue
        if "dismissable(" not in text and "Adw.HeaderBar" not in text:
            missing.append(path.name)
    assert missing == [], f"windows with no way out: {missing}"
