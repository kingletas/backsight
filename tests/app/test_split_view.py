"""Two editors, and which one your typing goes to.

Three menu items pointed at this since the menus were written. The reason it was
not built is that the window reaches into the editor from eighty-nine places —
so none of them decides which pane it meant: `_files_open` is whichever pane has
the keyboard, and every call site follows the focus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk  # noqa: E402

from backsight.app.window import Window  # noqa: E402

WORKSPACE = Path(__file__).resolve().parents[2] / "fixtures" / "stacks" / "plain" / "infra"
FILES = sorted(WORKSPACE.rglob("main.tf"))


@pytest.fixture
def window():
    found = Window()
    found.open_workspace(WORKSPACE)
    return found


def test_it_opens_with_one_pane(window):
    assert not window._editors.is_split
    assert len(window._editors.panes) == 1


def test_splitting_makes_a_second_and_puts_the_keyboard_in_it(window):
    window.open_file(FILES[0])
    window.split_right()
    assert window._editors.is_split
    assert window._files_open is window._editors.panes[1]


def test_the_file_in_front_comes_with_you(window):
    """A second pane that opens empty is one somebody has to fill before it is
    worth anything."""
    window.open_file(FILES[0])
    window.split_right()
    assert window._files_open.current is not None
    assert window._files_open.current.path == FILES[0].resolve()


def test_splitting_again_turns_it_rather_than_making_a_third(window):
    """Editors that split without limit are editors people get lost in."""
    window.open_file(FILES[0])
    window.split_right()
    window.split_down()
    assert len(window._editors.panes) == 2
    assert window._editors._paned.get_orientation() is Gtk.Orientation.VERTICAL


def test_every_call_site_follows_the_focus_without_knowing(window):
    """`_files_open` is the whole mechanism. Nothing else in the window learned
    that a split exists."""
    window.open_file(FILES[0])
    window.split_right()
    window.open_file(FILES[1])
    assert window._files_open.current.path == FILES[1].resolve()
    window._editors.focus_other()
    assert window._files_open.current.path == FILES[0].resolve()


def test_the_two_panes_hold_different_files(window):
    window.open_file(FILES[0])
    window.split_right()
    window.open_file(FILES[1])
    first, second = window._editors.panes
    assert set(first.pages) == {FILES[0].resolve()}
    assert set(second.pages) == {FILES[0].resolve(), FILES[1].resolve()}


def test_cloning_puts_the_same_file_in_both(window):
    """For reading two parts of one long file."""
    window.open_file(FILES[0])
    window.clone_into_split()
    first, second = window._editors.panes
    assert FILES[0].resolve() in first.pages
    assert FILES[0].resolve() in second.pages


def test_cloning_with_nothing_open_says_so_rather_than_splitting(window):
    said = []
    window._say = said.append
    window.clone_into_split()
    assert not window._editors.is_split
    assert said == ["Open a file to put it in a split"]


def test_going_back_to_one_pane_keeps_the_one_you_were_in(window):
    window.open_file(FILES[0])
    window.split_right()
    window.open_file(FILES[1])
    keeping = window._files_open
    window.unsplit()
    assert not window._editors.is_split
    assert window._files_open is keeping
    assert FILES[1].resolve() in window._files_open.pages


def test_unsplitting_when_there_is_one_pane_does_nothing(window):
    window.unsplit()
    assert len(window._editors.panes) == 1


def test_the_actions_are_registered(window):
    live = set(window.list_actions())
    assert {"split-right", "split-down", "clone-into-split", "unsplit"} <= live
