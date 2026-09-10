"""Returning somebody to where they were, and never failing a launch to do it."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.layout.session import (
    GEOMETRY,
    SESSION,
    Geometry,
    OpenFile,
    Session,
    directory,
    read_geometry,
    read_session,
    remember_geometry,
    remember_session,
)


def test_the_window_comes_back_the_size_it_was(tmp_path: Path):
    remember_geometry(Geometry(width=1000, height=700, maximised=True, sidebar=310), home=tmp_path)
    found = read_geometry(home=tmp_path)
    assert (found.width, found.height, found.maximised, found.sidebar) == (1000, 700, True, 310)


def test_a_first_launch_gets_a_usable_default(tmp_path: Path):
    assert read_geometry(home=tmp_path).is_sane


def test_a_window_too_small_to_use_is_refused(tmp_path: Path):
    """Restored at 40x12 nobody can find the edges to resize it back."""
    remember_geometry(Geometry(width=40, height=12), home=tmp_path)
    assert read_geometry(home=tmp_path) == Geometry()


def test_rubbish_in_the_file_costs_the_layout_and_not_the_launch(tmp_path: Path):
    path = directory(home=tmp_path) / GEOMETRY
    path.parent.mkdir(parents=True)
    path.write_text('{"width": "wide"}', encoding="utf-8")
    assert read_geometry(home=tmp_path) == Geometry()


def test_the_open_files_come_back_with_the_caret_where_it_was(tmp_path: Path):
    remember_session(
        "/src/acme",
        Session(files=[OpenFile("main.tf", line=42, column=7, scroll=0.3)], active="main.tf"),
        home=tmp_path,
    )
    found = read_session("/src/acme", home=tmp_path)
    assert found.active == "main.tf"
    assert (found.files[0].line, found.files[0].column) == (42, 7)


def test_each_workspace_keeps_its_own(tmp_path: Path):
    remember_session("/src/a", Session(files=[OpenFile("a.tf")]), home=tmp_path)
    remember_session("/src/b", Session(files=[OpenFile("b.tf")]), home=tmp_path)
    assert read_session("/src/a", home=tmp_path).files[0].path == "a.tf"
    assert read_session("/src/b", home=tmp_path).files[0].path == "b.tf"


def test_a_workspace_never_opened_has_nothing_to_restore(tmp_path: Path):
    assert read_session("/src/new", home=tmp_path).is_empty


def test_an_entry_with_no_path_is_dropped_rather_than_restored(tmp_path: Path):
    import json

    path = directory(home=tmp_path) / SESSION
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"/src/a": {"files": [{"line": 3}, {"path": "ok.tf"}], "active": ""}}),
        encoding="utf-8",
    )
    found = read_session("/src/a", home=tmp_path)
    assert [f.path for f in found.files] == ["ok.tf"]


def test_a_broken_entry_does_not_take_the_good_ones_with_it(tmp_path: Path):
    import json

    path = directory(home=tmp_path) / SESSION
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"/src/a": {"files": [{"path": "bad.tf", "line": "x"}, {"path": "ok.tf"}]}}),
        encoding="utf-8",
    )
    assert [f.path for f in read_session("/src/a", home=tmp_path).files] == ["ok.tf"]


def test_a_line_number_is_never_restored_below_one(tmp_path: Path):
    remember_session("/src/a", Session(files=[OpenFile("a.tf", line=-5)]), home=tmp_path)
    assert read_session("/src/a", home=tmp_path).files[0].line == 1


def test_saving_never_raises_when_the_state_directory_cannot_be_written(tmp_path: Path):
    """Losing a layout is not worth failing a shutdown over."""
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    remember_geometry(Geometry(), home=blocked)
    remember_session("/src/a", Session(), home=blocked)
