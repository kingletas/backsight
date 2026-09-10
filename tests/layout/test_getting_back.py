"""Sheet 12's invariant: nothing can be hidden in a way that traps you.

Configurability is added one setting at a time, and the fifth one is where
somebody ships a combination that leaves a panel whose only toggle lived inside
the panel it hides. That is a test, not a principle.
"""

import pytest

from backsight.engine.layout.panels import (
    PANELS,
    LastBrowsableSurface,
    Layout,
    Visibility,
    restore_paths,
)
from backsight.engine.settings.keys import THE_FLOOR, Keymap, Unbindable


@pytest.fixture
def keymap():
    return Keymap.build()


# --- the invariant --------------------------------------------------------


def test_with_everything_hidden_every_panel_is_still_reachable_two_ways(keymap):
    """The test sheet 12 asks for, run against the state it warns about."""
    layout = Layout.default()
    layout.hide_everything()
    for panel in PANELS:
        paths = restore_paths(panel, keymap)
        assert paths["keyboard"], f"{panel.label} has no keyboard path back"
        assert paths["mouse"], f"{panel.label} has no mouse path back"


def test_every_panel_has_two_independent_paths_not_the_same_one_twice(keymap):
    for panel in PANELS:
        paths = restore_paths(panel, keymap)
        assert len(set(paths["keyboard"]) | set(paths["mouse"])) >= 2, panel.label


def test_the_palette_can_reach_every_panel(keymap):
    """Which is what makes a panel with no dedicated key still recoverable."""
    for panel in PANELS:
        assert any("→" in path for path in panel.keyboard_paths(keymap)), panel.label


def test_a_panel_with_no_shortcut_is_still_reachable(keymap):
    """The status bar has no key of its own, and must not need one."""
    status = next(p for p in PANELS if p.name == "status_bar")
    assert status.action is None
    paths = restore_paths(status, keymap)
    assert paths["keyboard"] and paths["mouse"]


# --- the last browsable surface -------------------------------------------


def test_the_menu_bar_is_off_to_begin_with():
    """Its eight menus are in the primary menu, so with the bar on they would
    be in two places at once — and the row itself ran 62% empty while costing
    28 pixels of every screen."""
    assert Layout.default().visibility("menu_bar") is Visibility.HIDDEN


def test_the_primary_menu_is_always_there():
    layout = Layout.default()
    assert layout.visibility("hamburger") is Visibility.SHOWN
    layout.set("menu_bar", Visibility.SHOWN)
    assert layout.visibility("hamburger") is Visibility.SHOWN
    layout.set("menu_bar", Visibility.HIDDEN)
    assert layout.visibility("hamburger") is Visibility.SHOWN


def test_hiding_the_last_browsable_surface_is_refused():
    """Sheet 12: hiding the last one is refused, not permitted with a warning."""
    layout = Layout.default()
    with pytest.raises(LastBrowsableSurface, match="last surface that can be browsed"):
        layout.set("hamburger", Visibility.HIDDEN)


def test_hiding_everything_still_leaves_something_browsable():
    layout = Layout.default()
    layout.hide_everything()
    assert any(p.browsable and layout.is_shown(p.name) for p in PANELS)


# --- collapsed is not hidden ----------------------------------------------


def test_the_rail_opens_shown_and_collapses_to_a_strip():
    """It is how somebody finds a file, so opening folded away is the workbench
    hiding its own navigation. Collapsed is where the toggle goes, and a strip
    costs a few pixels and prevents losing a feature by mis-click.

    There is one rail. The second held four short sections against a column of
    empty space, and everything it carried is in this one now.
    """
    layout = Layout.default()
    assert layout.visibility("left_rail") is Visibility.SHOWN
    layout.toggle("left_rail")
    assert layout.visibility("left_rail") is Visibility.COLLAPSED


def test_collapsed_can_still_be_clicked_and_hidden_cannot():
    assert Visibility.COLLAPSED.is_reachable_by_pointing is True
    assert Visibility.HIDDEN.is_reachable_by_pointing is False


def test_toggling_a_collapsible_panel_never_reaches_hidden():
    """Toggling is a two-state operation; hiding is a deliberate one."""
    layout = Layout.default()
    for _ in range(6):
        assert layout.toggle("left_rail") is not Visibility.HIDDEN


def test_toggling_a_panel_that_cannot_collapse_hides_it():
    layout = Layout.default()
    layout.set("plan_drawer", Visibility.SHOWN)
    assert layout.toggle("plan_drawer") is Visibility.HIDDEN


def test_asking_a_non_collapsible_panel_to_collapse_hides_it_instead():
    layout = Layout.default()
    layout.set("console", Visibility.COLLAPSED)
    assert layout.visibility("console") is Visibility.HIDDEN


# --- reset ----------------------------------------------------------------


def test_reset_layout_returns_everything_to_its_default():
    """The universal escape from any configuration somebody got into."""
    layout = Layout.default()
    layout.hide_everything()
    layout.reset()
    for panel in PANELS:
        assert layout.visibility(panel.name) is panel.default


# --- the floor ------------------------------------------------------------


def test_the_two_floor_commands_cannot_be_unbound():
    for action in THE_FLOOR:
        with pytest.raises(Unbindable, match="cannot be unbound"):
            Keymap.build({action: None})


def test_the_floor_commands_have_keys_by_default(keymap):
    for action in THE_FLOOR:
        assert keymap.accelerator(action)


def test_any_other_binding_may_be_removed():
    keymap = Keymap.build({"toggle-console": None})
    assert keymap.accelerator("toggle-console") is None
