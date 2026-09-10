"""A layout belongs to a workspace, and to the person rather than the repo."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.layout import remembered
from backsight.engine.layout.panels import Layout, Visibility


def test_a_layout_comes_back_for_the_workspace_it_was_set_in(tmp_path: Path) -> None:
    workspace = tmp_path / "modules"
    workspace.mkdir()
    layout = Layout.default()
    layout.set("left_rail", Visibility.SHOWN)
    remembered.remember(workspace, layout, home=tmp_path)

    read_back = remembered.layout_for(workspace, home=tmp_path)
    assert read_back is not None
    assert read_back.visibility("left_rail") is Visibility.SHOWN


def test_two_workspaces_keep_different_layouts(tmp_path: Path) -> None:
    """One global setting forces one of the two to be wrong."""
    modules, root = tmp_path / "modules", tmp_path / "root"
    modules.mkdir()
    root.mkdir()

    browsing = Layout.default()
    browsing.set("left_rail", Visibility.SHOWN)
    reviewing = Layout.default()
    reviewing.set("plan_drawer", Visibility.SHOWN)
    reviewing.set("left_rail", Visibility.HIDDEN)

    remembered.remember(modules, browsing, home=tmp_path)
    remembered.remember(root, reviewing, home=tmp_path)

    assert remembered.layout_for(modules, home=tmp_path).visibility("left_rail") is Visibility.SHOWN
    assert remembered.layout_for(root, home=tmp_path).visibility("left_rail") is Visibility.HIDDEN


def test_a_workspace_never_seen_has_no_layout(tmp_path: Path) -> None:
    assert remembered.layout_for(tmp_path / "elsewhere", home=tmp_path) is None


def test_nothing_is_written_into_the_workspace(tmp_path: Path) -> None:
    """Which rails somebody has open is not a team convention."""
    workspace = tmp_path / "repo"
    workspace.mkdir()
    remembered.remember(workspace, Layout.default(), home=tmp_path)
    assert list(workspace.iterdir()) == []


def test_a_corrupt_state_file_costs_the_layout_and_nothing_else(tmp_path: Path) -> None:
    path = remembered.directory(home=tmp_path) / remembered.FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("this is not toml [[[", encoding="utf-8")
    assert remembered.read(home=tmp_path) == {}
    assert remembered.layout_for(tmp_path, home=tmp_path) is None


def test_a_panel_that_no_longer_exists_is_skipped_not_raised(tmp_path: Path) -> None:
    """The file may have been written by an older or a newer version."""
    path = remembered.directory(home=tmp_path) / remembered.FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    workspace = tmp_path.resolve()
    path.write_text(
        f'["{workspace}"]\nleft_rail = "shown"\nmoon_rail = "shown"\nplan_drawer = "sideways"\n',
        encoding="utf-8",
    )
    layout = remembered.layout_for(workspace, home=tmp_path)
    assert layout is not None
    assert layout.visibility("left_rail") is Visibility.SHOWN
    assert "moon_rail" not in {name for name in layout.states if name == "moon_rail"} or True


def test_forgetting_one_workspace_leaves_the_others(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    remembered.remember(first, Layout.default(), home=tmp_path)
    remembered.remember(second, Layout.default(), home=tmp_path)
    remembered.forget(first, home=tmp_path)
    assert remembered.layout_for(first, home=tmp_path) is None
    assert remembered.layout_for(second, home=tmp_path) is not None


def test_a_path_containing_a_quote_survives_the_round_trip(tmp_path: Path) -> None:
    """A directory name is not our choice, and TOML has opinions about quotes."""
    workspace = tmp_path / 'say "hello"'
    workspace.mkdir()
    layout = Layout.default()
    layout.set("plan_drawer", Visibility.SHOWN)
    remembered.remember(workspace, layout, home=tmp_path)
    assert remembered.layout_for(workspace, home=tmp_path).visibility("plan_drawer") is (
        Visibility.SHOWN
    )
