"""The sidebar is the tree, and the plan lives on the right.

The sidebar was four unrelated things in one column: the tree squeezed into the
top fifth, and below it three paragraphs explaining features somebody was not
using.
"""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.window import Window  # noqa: E402

WORKSPACE = Path(__file__).resolve().parents[2] / "fixtures" / "workspace"


@pytest.fixture
def window():
    return Window()


def _labels(widget, found=None):
    from gi.repository import Gtk

    found = [] if found is None else found
    if isinstance(widget, Gtk.Label):
        found.append(widget.get_text())
    child = widget.get_first_child()
    while child is not None:
        _labels(child, found)
        child = child.get_next_sibling()
    return found


# --- the sidebar -----------------------------------------------------------


def test_the_sidebar_no_longer_carries_stacks_the_plan_or_drift(window):
    """Three paragraphs teaching features to somebody who is not using them,
    on every launch, forever."""
    said = " ".join(_labels(window._sidebar_widget))
    assert "Group modules that deploy together" not in said
    assert "Monthly cost" not in said
    assert "Drift check" not in said


def test_the_tree_takes_the_height(window):
    """No empty region below it at any window height."""
    from gi.repository import Gtk

    scrollers = []

    def walk(widget):
        if isinstance(widget, Gtk.ScrolledWindow):
            scrollers.append(widget)
        child = widget.get_first_child()
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(window._sidebar_widget)
    assert any(one.get_vexpand() for one in scrollers)


def test_the_rail_is_files_and_nothing_else(window):
    """No heading over the only section there is, no count of rows, and no
    footer. Each of those was a slice of height taken from the tree, which is
    the only thing in the rail somebody came to look at."""
    window.open_workspace(WORKSPACE)
    window.show_workspace_heading()
    assert not hasattr(window, "_workspace_name")
    assert not hasattr(window, "_modules_summary")


def test_what_the_workspace_is_moved_to_the_switcher(window):
    """The name, the backend and the state are where somebody switching
    workspaces is already looking."""
    window.open_workspace(WORKSPACE)
    found = window._known_workspace()
    assert found is not None
    assert found.path == WORKSPACE
    assert found.backend


def test_the_filter_is_not_resident_either(window):
    """A search field sitting empty over a tree is a row of height spent on a
    control nobody has reached for."""
    window.open_workspace(WORKSPACE)
    assert not window._rail_filter.get_visible()


def test_escape_puts_the_whole_tree_back_and_takes_the_field_with_it(window):
    window.open_workspace(WORKSPACE)
    window._rail_filter.set_visible(True)
    window._rail_filter.set_text("main")
    assert window.clear_the_rail_filter()
    assert not window._rail_filter.get_visible()
    assert window._rail_filter.get_text() == ""


# --- what the inspector used to answer -------------------------------------


def test_there_is_no_right_hand_inspector(window):
    """It answered the same five questions the drawer answers, in a permanent
    320-pixel column too narrow for any of them."""
    assert not hasattr(window, "inspector")
    assert "inspector" not in window._panels


def test_the_plan_is_the_drawer(window):
    assert "Changes" in window._drawer.sections


def test_drift_is_a_chip_and_only_when_there_is_drift(window):
    """A row that is always there and always says nothing is a row people stop
    reading. It was in the inspector, in bold, forever."""
    window._refresh_drift_rail()
    assert "drifted" not in " ".join(window._status_line.texts())


def test_when_something_has_drifted_it_says_so(window):
    window.update_status(drifted=3)
    assert "3 drifted" in window._status_line.texts()
