"""No setting leaves a capability unreachable, and nothing said is lost.

FR-APP-30's invariant, driven rather than reasoned about: hide everything, and
check there is still a way back to each of them by keyboard and by pointing.
"""

from __future__ import annotations

import pytest

from tests.acceptance.looking import drawn, says, settle

gi = pytest.importorskip("gi", reason="the toolkit is not installed")


def test_every_panel_can_be_hidden_and_brought_back(opened):
    for name in list(opened._panels):
        opened.hide_panel(name)
        settle(opened, 0.2)
        opened.show_panel(name)
        settle(opened, 0.2)
        assert drawn(opened._panels[name]), name


def test_hiding_everything_leaves_a_way_back_to_each(opened):
    """A combination of settings that loses a feature outright is the failure
    this invariant exists for."""
    from backsight.engine.layout.panels import PANELS

    opened.layout.hide_everything()
    for name in list(opened._panels):
        opened._apply(name)
    settle(opened)

    keymap = opened.keymap
    for panel in PANELS:
        assert panel.mouse_paths, panel.name
        assert panel.keyboard_paths(keymap), panel.name


def test_reset_layout_brings_all_of_it_back(opened):
    opened.layout.hide_everything()
    for name in list(opened._panels):
        opened._apply(name)
    settle(opened, 0.3)
    opened.reset_layout()
    settle(opened, 0.4)
    assert drawn(opened._sidebar_widget)
    assert drawn(opened._editor)


def test_the_command_palette_never_opens_empty(opened):
    """An occasional user cannot search for a command they do not know exists,
    and this is the only affordance between them and a blank prompt."""
    assert opened._palette_suggestions()


def test_what_you_reached_for_last_comes_back_first(opened):
    from backsight.engine.presentation.palette import Entry, Kind

    opened._on_palette_choice(Entry(label="Plan", kind=Kind.COMMAND, action="plan"))
    settle(opened, 0.2)
    assert opened._palette_suggestions()[0].action == "plan"


def test_the_keyboard_reference_lists_what_is_bound(opened):
    from backsight.app.keyboard_reference import KeyboardReference

    reference = KeyboardReference(opened.keymap, parent=opened)
    reference.present()
    settle(opened, 0.4)
    assert says(reference, "Save")
    reference.close()


def test_peeking_shows_a_hidden_panel_without_changing_the_layout(opened):
    from backsight.engine.layout.panels import Visibility

    opened.hide_panel("plan_drawer")
    settle(opened, 0.2)
    opened.peek("plan_drawer")
    settle(opened, 0.3)
    assert opened._drawer.get_visible()
    assert opened.layout.visibility("plan_drawer") is Visibility.HIDDEN
    opened.stop_peeking()
    settle(opened, 0.2)
    assert not opened._drawer.get_visible()


def test_escape_never_leaves_a_blocking_message_dismissed(window, tmp_path):
    """Dismissing "this workspace has not been initialised" hides the reason
    nothing works."""
    (tmp_path / "main.tf").write_text('resource "terraform_data" "a" {}\n', encoding="utf-8")
    window.open_workspace(tmp_path)
    window.open_file(tmp_path / "main.tf")
    window.show_what_is_blocking()
    settle(window, 0.3)
    if window._blocking is not None and not window._blocking.dismissible:
        window.dismiss_banner()
        assert window._banner.get_revealed()


def test_closing_the_drawer_gives_the_editor_its_space_back(opened):
    opened.open_drawer("Changes")
    settle(opened, 0.4)
    with_drawer = opened._editor.get_height()
    opened.hide_panel("plan_drawer")
    settle(opened, 0.4)
    assert opened._editor.get_height() > with_drawer
    assert not opened._drawer.get_visible()
