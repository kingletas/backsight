"""Everything on screen has room to be seen.

The failure this exists for: the inspector's width was computed before the
window had been laid out, so it divided a width of zero, and the editor — the
thing the application is for — drew nothing. The unit suite was entirely green.
"""

from __future__ import annotations

import pytest

from tests.acceptance.looking import drawn, settle

gi = pytest.importorskip("gi", reason="the toolkit is not installed")


def test_the_editor_has_room_to_be_seen(opened):
    """The one that broke. It is what the application is for."""
    assert drawn(opened._editor)
    assert opened._editor.get_width() > 400


def test_the_sidebar_has_room(opened):
    assert drawn(opened._sidebar_widget)
    assert opened._sidebar_widget.get_width() > 100


def test_the_buffer_got_the_inspectors_room(opened):
    """Three hundred and twenty pixels of permanent column went to the thing
    the window is for."""
    assert opened._editor.get_width() > 600


def test_the_status_bar_has_room(opened):
    assert drawn(opened._status_widget)


def test_the_drawer_has_room_once_it_is_open(opened):
    opened.open_drawer("Changes")
    settle(opened)
    assert drawn(opened._drawer)


def test_no_panel_takes_the_editor_to_nothing(opened):
    """Every panel on at once still leaves an editor to type in."""
    for name in ("left_rail", "plan_drawer", "status_bar"):
        opened.show_panel(name)
    settle(opened)
    assert opened._editor.get_width() > 300


def test_hiding_everything_still_leaves_the_editor(opened):
    opened.layout.hide_everything()
    for name in list(opened._panels):
        opened._apply(name)
    settle(opened)
    assert drawn(opened._editor)


def test_every_drawer_tab_draws_something(opened):
    """A tab with a panel behind it that draws nothing is a promise the drawer
    cannot keep."""
    for name in opened._drawer.sections:
        opened.open_drawer(name)
        settle(opened, 0.3)
        assert opened._drawer.section.lower() == name.lower(), name
        assert drawn(opened._drawer), name


def test_everything_still_has_room_with_the_drawer_open(opened):
    """Narrow on purpose. At a wide default there is room for everything and
    the layout never has to decide.

    A paned will happily give one of its children nothing, and a position
    computed before the window had a width is how the whole centre once went
    blank. Verified by putting the defect back and watching this go red.
    """
    opened.open_drawer("Changes")
    settle(opened)
    opened.set_default_size(900, 700)
    settle(opened, 0.8)
    assert opened._sidebar_widget.get_width() > 100
    assert opened._editor.get_width() > 200


def test_the_whole_layout_survives_a_small_window(opened):
    """An adaptive layout is a Must, and a laptop at 1366 with a sidebar open
    is the ordinary case rather than the awkward one."""
    opened.open_drawer("Changes")
    opened.set_default_size(820, 620)
    settle(opened, 0.8)
    for name, widget in (
        ("sidebar", opened._sidebar_widget),
        ("editor", opened._editor),
        ("status bar", opened._status_widget),
    ):
        assert drawn(widget), name
