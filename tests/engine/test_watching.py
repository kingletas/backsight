"""Noticing a file changed underneath the editor."""

from __future__ import annotations

import os
from pathlib import Path

from backsight.engine.workspace.watching import Change, Stamp, what_happened


def written(path: Path, text: str, when: int | None = None) -> None:
    path.write_text(text, encoding="utf-8")
    if when is not None:
        os.utime(path, ns=(when, when))


def test_an_untouched_file_reads_as_untouched(tmp_path: Path):
    path = tmp_path / "main.tf"
    written(path, "a")
    assert what_happened(Stamp.of(path), path) == Change.NOTHING


def test_a_rewritten_file_is_noticed(tmp_path: Path):
    path = tmp_path / "main.tf"
    written(path, "a", when=1_000_000_000)
    stamp = Stamp.of(path)
    written(path, "bb", when=2_000_000_000)
    assert what_happened(stamp, path) == Change.EDITED


def test_a_change_of_the_same_length_is_still_noticed(tmp_path: Path):
    """`fmt` and a branch switch often keep the size and never the time."""
    path = tmp_path / "main.tf"
    written(path, "aa", when=1_000_000_000)
    stamp = Stamp.of(path)
    written(path, "bb", when=2_000_000_000)
    assert what_happened(stamp, path) == Change.EDITED


def test_a_deleted_file_says_so_rather_than_edited(tmp_path: Path):
    path = tmp_path / "main.tf"
    written(path, "a")
    stamp = Stamp.of(path)
    path.unlink()
    assert what_happened(stamp, path) == Change.DELETED


def test_a_buffer_never_written_has_not_been_deleted(tmp_path: Path):
    path = tmp_path / "untitled.tf"
    assert what_happened(Stamp.of(path), path) == Change.NOTHING


def test_a_file_appearing_where_there_was_none_is_an_edit(tmp_path: Path):
    path = tmp_path / "main.tf"
    stamp = Stamp.of(path)
    written(path, "a")
    assert what_happened(stamp, path) == Change.EDITED


def test_a_stamp_of_a_missing_file_says_it_is_missing(tmp_path: Path):
    assert not Stamp.of(tmp_path / "nope.tf").exists


def test_a_path_that_cannot_be_stat_ed_is_absent_rather_than_an_error(tmp_path: Path):
    """A path *through* a file is an OSError, not a FileNotFoundError."""
    blocked = tmp_path / "a-file"
    blocked.write_text("x", encoding="utf-8")
    assert not Stamp.of(blocked / "under" / "it").exists
