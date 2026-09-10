"""Four layers, and being able to say which one won."""

from pathlib import Path

import pytest

from backsight.engine.settings.keys import (
    DEFAULTS as KEY_DEFAULTS,
)
from backsight.engine.settings.keys import (
    Keymap,
    desktop_conflicts,
)
from backsight.engine.settings.layers import DEFAULTS, Settings, Unreadable, flatten, load, read


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


# --- precedence -----------------------------------------------------------


def test_a_later_layer_wins_key_by_key():
    settings = Settings(
        layers={
            "default": {"editor.tab_size": 4, "terraform.binary": "tofu"},
            "user": {"editor.tab_size": 2},
        }
    )
    assert settings.get("editor.tab_size") == 2
    assert settings.get("terraform.binary") == "tofu"


def test_the_narrowest_layer_wins_outright():
    settings = Settings(
        layers={
            "default": {"editor.tab_size": 4},
            "user": {"editor.tab_size": 2},
            "workspace": {"editor.tab_size": 8},
            "language": {"editor.tab_size": 2},
        }
    )
    assert settings.get("editor.tab_size") == 2
    assert settings.source("editor.tab_size") == "language"


def test_explain_shows_the_winner_and_the_losers():
    """Without this, "why is my setting not applying" has no answer."""
    settings = Settings(
        layers={
            "default": {"terraform.format_on_save": False},
            "user": {"terraform.format_on_save": True},
            "workspace": {"terraform.format_on_save": False},
        }
    )
    explained = settings.explain("terraform.format_on_save")
    assert [(s.layer, s.value, s.in_effect) for s in explained] == [
        ("default", False, False),
        ("user", True, False),
        ("workspace", False, True),
    ]


def test_an_unset_key_falls_back_to_the_shipped_default():
    assert Settings().get("terraform.binary") == "tofu"
    assert Settings().source("terraform.binary") == "default"


# --- reading files --------------------------------------------------------


def test_a_nested_table_flattens_to_dotted_keys():
    assert flatten({"files": {"open_on": "single_click"}}) == {"files.open_on": "single_click"}


def test_a_missing_settings_file_is_simply_empty(tmp_path):
    assert read(tmp_path / "nothing.toml") == {}


def test_a_settings_file_that_will_not_parse_is_refused_by_name(tmp_path):
    """Ignoring a file somebody wrote costs them an afternoon."""
    broken = write(tmp_path / "settings.toml", "[files\nopen_on = 'x'\n")
    with pytest.raises(Unreadable, match="could not be read"):
        read(broken)


def test_the_four_layers_load_from_where_they_live(tmp_path):
    home = tmp_path / "home"
    workspace = tmp_path / "repo"
    write(home / ".config" / "backsight" / "settings.toml", "[editor]\ntab_size = 2\n")
    write(workspace / ".backsight" / "settings.toml", "[terraform]\nformat_on_save = true\n")
    write(home / ".config" / "backsight" / "settings.hcl.toml", "[editor]\ntab_size = 8\n")

    settings = load(workspace, home=home)
    assert settings.get("editor.tab_size") == 8
    assert settings.source("editor.tab_size") == "language"
    assert settings.get("terraform.format_on_save") is True
    assert settings.source("terraform.format_on_save") == "workspace"


# --- the defaults that carry a reason -------------------------------------


def test_formatting_on_save_is_off_because_round_trip_safety_is_a_hard_constraint():
    assert DEFAULTS["terraform.format_on_save"] is False


def test_planning_on_save_is_on_because_the_live_plan_is_the_product():
    assert DEFAULTS["terraform.plan_on_save"] is True


def test_convergence_on_save_is_off_because_it_starts_a_container():
    assert DEFAULTS["analysis.convergence_on_save"] is False


def test_the_rail_opens_shown():
    """It is how somebody finds a file. Opening folded away is the workbench
    hiding its own navigation — and "collapsed" sat here as a default nothing
    read until reading it started the app in that state."""
    assert DEFAULTS["layout.left_rail"] == "shown"


def test_a_stale_plan_marker_is_cleared_rather_than_dimmed():
    assert DEFAULTS["tabs.indicators.clear_plan_on_edit"] is True


# --- keys -----------------------------------------------------------------


def test_the_primary_modifier_is_control_and_never_super():
    """Super belongs to the desktop shell, which already owns four of these."""
    for command in KEY_DEFAULTS:
        if command.accelerator:
            assert "<Super>" not in command.accelerator, command.action


def test_a_binding_can_be_changed():
    keymap = Keymap.build({"plan": "<Control><Shift>Return"})
    assert keymap.accelerator("plan") == "<Control><Shift>Return"


def test_binding_something_that_does_not_exist_is_refused():
    with pytest.raises(KeyError, match="no command named"):
        Keymap.build({"invented-command": "<Control>z"})


def test_two_commands_on_one_key_are_reported_and_not_silently_resolved():
    """FR-APP-27. Load order deciding it makes the cause invisible."""
    keymap = Keymap.build({"toggle-console": "<Control>p"})
    conflicts = keymap.conflicts()
    assert len(conflicts) == 1
    assert conflicts[0].accelerator == "<Control>p"
    assert conflicts[0].actions == ("goto-file", "toggle-console")
    assert "bound to" in str(conflicts[0])


def test_the_shipped_keymap_has_no_conflicts():
    assert Keymap.build().conflicts() == []


def test_a_binding_the_desktop_would_take_first_is_named():
    """An application cannot win that argument, so it should say which key is dead."""
    keymap = Keymap.build({"plan": "<Super>p"})
    found = desktop_conflicts(keymap, {"<Super>p"})
    assert found and "taken by the desktop" in found[0]


def test_the_keyboard_reference_groups_by_section():
    sections = Keymap.build().sections()
    assert {"Panels", "Navigate", "Terraform", "File"} <= set(sections)
    assert all(
        commands == sorted(commands, key=lambda c: c.label) for commands in sections.values()
    )
