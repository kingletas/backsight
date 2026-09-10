"""Diff, history and blame against a real repository — and a discard that returns."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from backsight.engine.vcs.history import blame, diff, discard, history


def repository(tmp_path: Path) -> Path:
    """A real repository, invented from nothing."""
    run = lambda *args: subprocess.run(  # noqa: E731
        args, cwd=tmp_path, check=True, capture_output=True
    )
    run("git", "init", "-q", ".")
    run("git", "config", "user.email", "nobody@example.invalid")
    run("git", "config", "user.name", "Nobody")
    path = tmp_path / "main.tf"
    path.write_text('resource "terraform_data" "a" {\n  input = "one"\n}\n')
    run("git", "add", "-A")
    run("git", "commit", "-qm", "first")
    return path


def test_a_clean_file_has_no_diff(tmp_path):
    assert diff(repository(tmp_path)) == ""


def test_a_changed_file_shows_what_changed(tmp_path):
    path = repository(tmp_path)
    path.write_text('resource "terraform_data" "a" {\n  input = "two"\n}\n')
    shown = diff(path)
    assert '-  input = "one"' in shown
    assert '+  input = "two"' in shown


def test_history_names_the_commits_that_touched_it(tmp_path):
    found = history(repository(tmp_path))
    assert len(found) == 1
    assert found[0].subject == "first"
    assert found[0].author == "Nobody"
    assert len(found[0].short) == 8


def test_blame_gives_a_commit_for_every_line(tmp_path):
    found = blame(repository(tmp_path))
    assert [line.number for line in found] == [1, 2, 3]
    assert all(line.author == "Nobody" for line in found)


def test_discarding_stashes_rather_than_throwing_away(tmp_path):
    """`git checkout --` loses uncommitted work with nothing to recover it."""
    path = repository(tmp_path)
    path.write_text("edited\n")
    stashed = discard(path)
    assert stashed.recoverable
    assert path.read_text() != "edited\n"

    subprocess.run(["git", "stash", "pop", "-q"], cwd=tmp_path, check=True, capture_output=True)
    assert path.read_text() == "edited\n"


def test_discarding_a_file_with_nothing_to_discard_says_so(tmp_path):
    stashed = discard(repository(tmp_path))
    assert not stashed.recoverable
    assert "nothing to discard" in str(stashed)


def test_a_file_outside_a_repository_reports_nothing_rather_than_raising(tmp_path):
    path = tmp_path / "loose.tf"
    path.write_text("body\n")
    assert history(path) == []
    assert blame(path) == []


@pytest.mark.parametrize("subject", ["a subject", "one: with a colon"])
def test_a_commit_subject_survives_whatever_is_in_it(tmp_path, subject):
    path = repository(tmp_path)
    path.write_text("second\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", subject], cwd=tmp_path, check=True, capture_output=True)
    assert history(path)[0].subject == subject
