"""A double click in the rail is a double click, however fast it is.

**A quick double click was read as one click.** The rail's list activates on a
single click, and the toolkit only activates on the first press of a click
sequence — so the second press of a fast double click never arrived, and only
two clicks a second apart registered as two. Every test of this called the
window's handler with a press count of two, which is exactly the part that was
never broken.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.offscreen import use_a_private_display  # noqa: E402

use_a_private_display()

from gi.repository import GLib, Gtk  # noqa: E402

from backsight.app.file_tree import FileTree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "workspace"
FILE = ROOT / "environments" / "prod" / "main.tf"
FOLDER = ROOT / "environments"


def _pump(seconds: float = 0.5) -> None:
    ends = time.monotonic() + seconds
    while time.monotonic() < ends:
        GLib.MainContext.default().iteration(False)


@pytest.fixture
def tree():
    opened: list[tuple[str, int]] = []
    found = FileTree(on_open=lambda path, presses: opened.append((path.name, presses)))
    holder = Gtk.Window(default_width=320, default_height=600)
    holder.set_child(found)
    holder.present()
    found.show(ROOT)
    found.reveal(FILE)
    _pump()
    found.opened = opened
    yield found
    holder.destroy()


def _double_click_gesture(tree: FileTree) -> Gtk.GestureClick:
    return next(
        one
        for one in tree._list.observe_controllers()
        if isinstance(one, Gtk.GestureClick)
        and one.get_propagation_phase() == Gtk.PropagationPhase.CAPTURE
    )


def _centre_of(tree: FileTree, path: Path) -> tuple[float, float]:
    row = tree.rows[path][0]
    _found, box = row.compute_bounds(tree._list)
    return box.origin.x + 20, box.origin.y + box.size.height / 2


def test_the_second_press_of_a_fast_double_click_keeps_the_file(tree):
    x, y = _centre_of(tree, FILE)
    _double_click_gesture(tree).emit("pressed", 2, x, y)
    assert tree.opened == [("main.tf", 2)]


def test_the_first_press_is_left_to_the_single_click(tree):
    """One path for a single click, so a single click cannot open twice."""
    x, y = _centre_of(tree, FILE)
    _double_click_gesture(tree).emit("pressed", 1, x, y)
    assert tree.opened == []


def test_a_double_click_on_a_folder_opens_no_file(tree):
    x, y = _centre_of(tree, FOLDER)
    _double_click_gesture(tree).emit("pressed", 2, x, y)
    assert tree.opened == []


def test_two_separate_clicks_are_two_previews_rather_than_a_keep(tree):
    """Only the toolkit's own press count says double. Two clicks a second
    apart are two single clicks, the way Sublime Text reads them."""
    model = tree._model
    at = next(
        index
        for index in range(model.get_n_items())
        if model.get_row(index).get_item().path == FILE
    )
    tree._activated(tree._list, at)
    tree._activated(tree._list, at)
    assert tree.opened == [("main.tf", 1), ("main.tf", 1)]
