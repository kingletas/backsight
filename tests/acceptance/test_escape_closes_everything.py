"""Escape gets you out of whatever is open, and it is driven rather than asserted.

**A real key press through the display**, not a call to the handler. The bug
this file exists for was invisible to any test that called the handler: the
palette's Escape handler was correct, connected and never reached, because
`Gtk.SearchEntry` installs its own Escape shortcut and stops the event before a
controller on the window can run.

So every case here presses the key the way a person does, and asks the
application what happened.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.acceptance.looking import settle
from tests.pressing import press_escape

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from gi.repository import Gtk  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "fixtures" / "workspace"
A_FILE = WORKSPACE / "environments" / "prod" / "main.tf"


def palettes() -> list[Gtk.Window]:
    return [one for one in Gtk.Window.get_toplevels() if type(one).__name__ == "Palette"]


@pytest.fixture
def opened(window):
    window.open_workspace(WORKSPACE)
    settle(window)
    return window


# --- the one in the screenshot ---------------------------------------------


def test_escape_closes_the_command_palette(opened):
    """**The reported bug.** The palette listened for Escape from the day it was
    written and Escape did nothing, because its search field ate the key."""
    opened.show_palette()
    settle(opened, 0.4)
    assert len(palettes()) == 1

    palette = palettes()[-1]
    press_escape(palette)
    settle(opened, 0.4)
    assert not palette.get_visible(), "the palette is still open"


def test_the_search_field_is_what_had_the_keyboard(opened):
    """Naming the cause, so a rewrite that reintroduces it fails here rather
    than in a screenshot months later."""
    opened.show_palette()
    settle(opened, 0.4)
    assert isinstance(palettes()[-1].get_focus(), Gtk.Text)


def test_it_closes_with_something_typed_into_it(opened):
    """A `Gtk.SearchEntry` with text in it consumes Escape *twice over* — once
    to clear, once to stop the search."""
    opened.show_palette()
    settle(opened, 0.4)
    palette = palettes()[-1]
    palette.entry.set_text("plan")
    settle(opened, 0.3)

    press_escape(palette)
    settle(opened, 0.4)
    assert not palette.get_visible()


def test_it_closes_from_every_prefix(opened):
    """Each prefix draws a different list; none of them changes who has focus,
    and that is worth holding still."""
    for prefix in (">", "@", ":", "#"):
        opened.show_palette(prefix)
        settle(opened, 0.3)
        palette = palettes()[-1]
        press_escape(palette)
        settle(opened, 0.3)
        assert not palette.get_visible(), f"the {prefix} palette is still open"


# --- what it does not do ---------------------------------------------------


def test_escape_does_not_reach_the_window_underneath(opened):
    """A press consumed by a modal is over. If it leaked, the drawer behind the
    palette would close at the same time — and the reader would have lost two
    things to one keystroke."""
    opened.open_drawer("Changes")
    settle(opened, 0.4)
    opened.show_palette()
    settle(opened, 0.4)
    palette = palettes()[-1]

    press_escape(palette)
    settle(opened, 0.4)
    assert not palette.get_visible()
    assert opened.layout.is_shown("plan_drawer"), "the drawer closed behind the palette"


def test_the_keyboard_comes_back_to_where_it_was(opened):
    """GTK returns focus to the parent window and stops there, which after a
    modal is usually the control that opened it rather than the buffer somebody
    was typing in."""
    opened.open_file(A_FILE, preview=False)
    settle(opened, 0.4)
    page = opened._files_open.current
    page.view.grab_focus()
    settle(opened, 0.2)

    opened.show_palette()
    settle(opened, 0.4)
    press_escape(palettes()[-1])
    settle(opened, 0.5)
    assert opened.get_focus() is page.view


# --- the same key, everything else it closes -------------------------------


def test_escape_closes_the_find_bar(opened):
    opened.open_file(A_FILE, preview=False)
    opened.show_find()
    settle(opened, 0.4)
    assert opened._find.get_visible()

    press_escape(opened)
    settle(opened, 0.4)
    assert not opened._find.get_visible()


def test_escape_closes_the_drawer(opened):
    opened.open_drawer("Changes")
    settle(opened, 0.4)
    press_escape(opened)
    settle(opened, 0.4)
    assert not opened.layout.is_shown("plan_drawer")


def test_escape_clears_the_rail_filter_before_anything_else(opened):
    """Outermost first: the thing you most recently opened is the thing you
    most likely meant."""
    opened.open_drawer("Changes")
    opened._rail_filter.set_visible(True)
    opened._rail_filter.set_text("main")
    settle(opened, 0.3)

    press_escape(opened)
    settle(opened, 0.3)
    assert not opened._rail_filter.get_visible()
    assert opened.layout.is_shown("plan_drawer"), "it took two things at once"

    press_escape(opened)
    settle(opened, 0.3)
    assert not opened.layout.is_shown("plan_drawer")


def test_escape_with_nothing_open_is_not_swallowed(opened):
    """An editor that eats every Escape for no reason is one where the key
    stops meaning anything."""
    assert opened._escape_dismissed_something() is False


# --- nested, and inside-out ------------------------------------------------


def others(main: Gtk.Window) -> list[Gtk.Window]:
    """Every window open on top of the main one.

    By identity, not by class name: the stacks view is an `Adw.Window`, whose
    `__name__` is also `Window`, so a name filter hid the very window this file
    was written about.
    """
    return [one for one in Gtk.Window.get_toplevels() if one.get_visible() and one is not main]


def test_a_modal_over_a_modal_closes_inside_out(opened):
    """One press each, outermost last. Only the topmost window has the keyboard,
    so this is what capture buys rather than something to arrange."""
    opened.show_stacks()
    settle(opened, 0.5)
    stacks = [one for one in others(opened) if one.get_title() == "Stacks"]
    assert stacks, "the stacks view did not open"

    opened.show_palette()
    settle(opened, 0.5)
    palette = palettes()[-1]

    press_escape(palette)
    settle(opened, 0.5)
    assert not palette.get_visible(), "the palette did not close"
    assert stacks[-1].get_visible(), "the window underneath closed too"

    press_escape(stacks[-1])
    settle(opened, 0.5)
    assert not stacks[-1].get_visible()


def test_a_window_with_no_header_bar_can_still_be_left(opened):
    """The failure this whole mechanism started from: a modal with no close
    button and nothing listening for Escape locked the application, and the
    only way out was to kill it."""
    opened.show_stacks()
    settle(opened, 0.5)
    stacks = [one for one in others(opened) if one.get_title() == "Stacks"][-1]
    press_escape(stacks)
    settle(opened, 0.5)
    assert not stacks.get_visible()


def test_a_question_is_answered_by_escape_with_the_harmless_answer(opened):
    """`Adw.MessageDialog` takes Escape itself; what matters is which response
    it maps to, and it is never the destructive one."""
    from gi.repository import Adw

    opened.open_file(A_FILE, preview=False)
    settle(opened, 0.3)
    opened._files_open.current.buffer.insert_at_cursor("# typed\n")
    opened.revert_current()
    settle(opened, 0.5)

    asked = [one for one in others(opened) if isinstance(one, Adw.MessageDialog)]
    assert asked, "reverting an edited file asked nothing"
    dialog = asked[-1]
    assert dialog.get_close_response() == "cancel"
    dialog.close()
    settle(opened, 0.3)
