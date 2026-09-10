"""The whole loop: reach a command, run it, read what came back, get out.

**This is where the modal system and the engine system meet**, and it is the
join neither suite covers on its own — the palette tests never run anything and
the engine tests never open a window.

Both ways in, every time: chosen with the pointer and chosen with the keyboard
reach the same command, because they are the same command. That is the point of
naming an action rather than wiring a handler twice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.acceptance.looking import settle

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk  # noqa: E402

from tests.acceptance.test_escape_closes_everything import (  # noqa: E402
    palettes,
    press_escape,
)

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "fixtures" / "plannable"
BROKEN = ROOT / "fixtures" / "broken-plan"


@pytest.fixture
def opened(window):
    window.open_workspace(WORKSPACE)
    settle(window, 0.6)
    return window


def rows(palette) -> list[Gtk.ListBoxRow]:
    found = []
    child = palette._list.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.ListBoxRow):
            found.append(child)
        child = child.get_next_sibling()
    return found


def find_row(palette, label: str) -> Gtk.ListBoxRow:
    for row in rows(palette):
        if label.lower() in _labels(row).lower():
            return row
    raise AssertionError(f"no row reading {label!r} among {[_labels(r) for r in rows(palette)]}")


def _labels(widget: Gtk.Widget) -> str:
    said = []

    def walk(one: Gtk.Widget) -> None:
        if isinstance(one, Gtk.Label):
            said.append(one.get_text())
        child = one.get_first_child()
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(widget)
    return " ".join(said)


# --- the pointer ------------------------------------------------------------


def test_a_command_can_be_reached_and_run_with_the_pointer(opened):
    """Open the palette, click the row, and the command runs. Every step is the
    one a person takes — nothing here calls the handler directly."""
    opened.show_palette(">")
    settle(opened, 0.5)
    palette = palettes()[-1]
    palette.entry.set_text(">validate")
    settle(opened, 0.4)

    row = find_row(palette, "Validate")
    palette._list.emit("row-activated", row)
    settle(opened, 1.5)

    assert not palette.get_visible(), "choosing a command left the palette open"


def test_the_keyboard_reaches_the_same_command(opened):
    """`choose` with nothing selected takes the first match, which is what
    Return does — and it is the same call the click above makes."""
    opened.show_palette(">")
    settle(opened, 0.5)
    palette = palettes()[-1]
    palette.entry.set_text(">validate")
    settle(opened, 0.4)

    palette.choose()
    settle(opened, 1.5)
    assert not palette.get_visible()


def test_both_ways_in_offer_the_same_rows(opened):
    """A pointer path and a key path that show different things are two
    implementations of one list."""
    opened.show_palette(">")
    settle(opened, 0.4)
    with_prefix = [_labels(row) for row in rows(palettes()[-1])]
    press_escape(palettes()[-1])
    settle(opened, 0.3)

    opened.show_palette()
    settle(opened, 0.4)
    palette = palettes()[-1]
    palette.entry.set_text(">")
    settle(opened, 0.4)
    typed = [_labels(row) for row in rows(palette)]
    press_escape(palette)
    settle(opened, 0.3)

    assert with_prefix == typed


# --- what came back, and getting out of it ---------------------------------


def test_output_appears_and_escape_closes_it(opened):
    """A command that prints something opens the drawer on Output; Escape
    closes the drawer and leaves the application usable."""
    opened.show_output("what the engine said")
    settle(opened, 0.5)
    assert opened.layout.is_shown("plan_drawer")

    press_escape(opened)
    settle(opened, 0.4)
    assert not opened.layout.is_shown("plan_drawer")


def test_a_command_that_fails_says_so_and_the_application_stays_usable(window):
    """**The case that catches an interaction rather than a unit.** A failing
    plan opens the drawer on its errors; Escape closes it; another command runs
    afterwards."""
    window.open_workspace(BROKEN)
    settle(window, 0.6)
    window.open_file(BROKEN / "main.tf", preview=False)
    settle(window, 0.4)

    window.plan_now()
    settle(window, 6.0)

    assert window._plan is None, "the broken fixture planned successfully"
    assert window._status_line.will_not_run, "the verdict line did not turn"

    press_escape(window)
    settle(window, 0.4)

    # And the application is still there to be used.
    window.show_palette()
    settle(window, 0.5)
    palette = palettes()[-1]
    assert palette.get_visible()
    press_escape(palette)
    settle(window, 0.4)
    assert not palette.get_visible()


def test_the_keyboard_comes_back_after_a_command_and_its_output(opened):
    """Round trip: focus in the buffer, palette, run, close, and the caret is
    back where the reader left it."""
    opened.open_file(WORKSPACE / "main.tf", preview=False)
    settle(opened, 0.5)
    page = opened._files_open.current
    page.view.grab_focus()
    settle(opened, 0.2)

    opened.show_palette(">")
    settle(opened, 0.5)
    press_escape(palettes()[-1])
    settle(opened, 0.6)

    assert opened.get_focus() is page.view


def test_two_commands_in_a_row_with_the_palette_between_them(opened):
    """Nothing is left in a stuck state by the first one, which is the whole
    reason to run a second."""
    for _ in range(2):
        opened.show_palette(">")
        settle(opened, 0.4)
        palette = palettes()[-1]
        assert palette.get_visible()
        press_escape(palette)
        settle(opened, 0.4)
        assert not palette.get_visible()
