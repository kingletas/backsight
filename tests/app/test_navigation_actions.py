"""Navigation moves the caret to somewhere real, or says why it did not."""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.window import Window  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "stacks" / "plain"
NETWORK = ROOT / "infra" / "network" / "main.tf"


@pytest.fixture
def window():
    made = Window()
    made.open_workspace(ROOT)
    made.open_file(NETWORK)
    return made


def caret(window) -> int:
    buffer = window._files_open.current.buffer
    return buffer.get_iter_at_mark(buffer.get_insert()).get_line() + 1


def put(window, line: int) -> None:
    window._files_open.current.go_to_line(line)


def test_moving_to_the_block_start_from_inside_it(window):
    put(window, 4)
    window.activate_action("win.goto-block-start", None)
    assert caret(window) == 3


def test_moving_to_the_block_end_from_inside_it(window):
    put(window, 4)
    window.activate_action("win.goto-block-end", None)
    assert caret(window) == 5


def test_selecting_the_enclosing_block_selects_all_of_it(window):
    put(window, 4)
    window.activate_action("win.select-enclosing-block", None)
    buffer = window._files_open.current.buffer
    start, end = buffer.get_selection_bounds()
    assert start.get_line() + 1 == 3
    assert end.get_line() + 1 == 5


def test_selecting_between_blocks_says_so_rather_than_selecting_something(window):
    put(window, 6)
    said: list[str] = []
    window._say = said.append
    window.activate_action("win.select-enclosing-block", None)
    assert said and "not inside a block" in said[0]


def test_going_to_a_definition_in_another_file_opens_that_file(window):
    """A reference is usually somewhere other than the declaration."""
    window.open_file(ROOT / "infra" / "data" / "main.tf")
    buffer = window._files_open.current.buffer
    buffer.set_text("terraform_data.vpc")
    buffer.select_range(buffer.get_start_iter(), buffer.get_end_iter())
    window.activate_action("win.goto-definition", None)
    assert window._files_open.current.path == NETWORK


def test_an_address_nothing_declares_is_reported_rather_than_guessed(window):
    buffer = window._files_open.current.buffer
    buffer.select_range(buffer.get_start_iter(), buffer.get_start_iter())
    said: list[str] = []
    window._say = said.append
    put(window, 1)
    window.activate_action("win.goto-definition", None)
    assert said and "Nothing under the caret" in said[0]


def test_finding_references_puts_the_address_in_the_find_row(window):
    put(window, 4)
    window.activate_action("win.find-references", None)
    assert window._find.get_visible()
    assert window._find.term.get_text() == "terraform_data.vpc"


def test_something_nothing_refers_to_says_so(window):
    put(window, 15)
    said: list[str] = []
    window._say = said.append
    window.activate_action("win.find-references", None)
    assert said and "Nothing refers to" in said[0]
