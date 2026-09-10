"""Unsaved work surviving the process dying."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.workspace.recovery import (
    directory,
    drop,
    drop_everything,
    is_still_different,
    keep,
    waiting,
)


def test_an_unsaved_buffer_comes_back(tmp_path: Path):
    file = tmp_path / "main.tf"
    keep(file, "half a resource", home=tmp_path)
    found = waiting(home=tmp_path)
    assert [f.text for f in found] == ["half a resource"]
    assert found[0].path == file


def test_nothing_is_waiting_after_a_clean_shutdown(tmp_path: Path):
    keep(tmp_path / "a.tf", "x", home=tmp_path)
    keep(tmp_path / "b.tf", "y", home=tmp_path)
    drop_everything(home=tmp_path)
    assert waiting(home=tmp_path) == []


def test_saving_one_file_forgets_only_that_one(tmp_path: Path):
    keep(tmp_path / "a.tf", "x", home=tmp_path)
    keep(tmp_path / "b.tf", "y", home=tmp_path)
    drop(tmp_path / "a.tf", home=tmp_path)
    assert [f.path.name for f in waiting(home=tmp_path)] == ["b.tf"]


def test_keeping_it_twice_keeps_the_newer_text(tmp_path: Path):
    file = tmp_path / "main.tf"
    keep(file, "first", home=tmp_path)
    keep(file, "second", home=tmp_path)
    assert [f.text for f in waiting(home=tmp_path)] == ["second"]


def test_two_files_with_the_same_name_do_not_collide(tmp_path: Path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    keep(tmp_path / "one" / "main.tf", "A", home=tmp_path)
    keep(tmp_path / "two" / "main.tf", "B", home=tmp_path)
    assert sorted(f.text for f in waiting(home=tmp_path)) == ["A", "B"]


def test_the_original_file_is_never_touched(tmp_path: Path):
    file = tmp_path / "main.tf"
    file.write_text("what is on disk", encoding="utf-8")
    keep(file, "what was being typed", home=tmp_path)
    assert file.read_text(encoding="utf-8") == "what is on disk"


def test_a_recovery_matching_the_file_is_not_a_recovery(tmp_path: Path):
    """A prompt about nothing is how people learn to dismiss the prompt."""
    file = tmp_path / "main.tf"
    file.write_text("same", encoding="utf-8")
    keep(file, "same", home=tmp_path)
    assert not is_still_different(waiting(home=tmp_path)[0])


def test_one_that_differs_is_worth_offering(tmp_path: Path):
    file = tmp_path / "main.tf"
    file.write_text("on disk", encoding="utf-8")
    keep(file, "in the buffer", home=tmp_path)
    assert is_still_different(waiting(home=tmp_path)[0])


def test_a_file_that_has_since_gone_is_still_worth_offering(tmp_path: Path):
    keep(tmp_path / "deleted.tf", "the only copy", home=tmp_path)
    assert is_still_different(waiting(home=tmp_path)[0])


def test_a_malformed_entry_never_stops_a_launch(tmp_path: Path):
    keep(tmp_path / "good.tf", "kept", home=tmp_path)
    (directory(home=tmp_path) / "broken.json").write_text("{ not json", encoding="utf-8")
    assert [f.text for f in waiting(home=tmp_path)] == ["kept"]


def test_failing_to_keep_a_copy_never_stops_typing(tmp_path: Path):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    keep(tmp_path / "a.tf", "x", home=blocked)


def test_nothing_waiting_on_a_fresh_machine(tmp_path: Path):
    assert waiting(home=tmp_path) == []
