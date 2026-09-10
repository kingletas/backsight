"""Staging, committing and pushing, against a real repository.

The status fixtures are real. The operations run against a repository built in
a temporary directory, because a fake `git` proves nothing about `git`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from backsight.engine.vcs.working import (
    State,
    branches,
    commit,
    create_branch,
    push,
    read_status,
    stage,
    status,
    switch,
    unstage,
)

FIXTURES = Path(__file__).resolve().parents[1].parent / "fixtures" / "git"
MIXED = (FIXTURES / "status-mixed.txt").read_text(encoding="utf-8")


# --- reading what git says --------------------------------------------------


def test_the_two_character_code_is_read_as_the_two_things_it_is():
    """`1 M.` is staged, `1 .M` is not, and a reader that treats it as one
    thing reports a file as staged when half of it is."""
    found = read_status(MIXED)
    by_path = {one.path: one.state for one in found.changes}
    assert by_path["c.txt"] is State.STAGED
    assert by_path["a.txt"] is State.CHANGED
    assert by_path["b.txt"] is State.UNTRACKED


def test_it_knows_the_branch():
    assert read_status(MIXED).branch == "main"


def test_staged_and_unstaged_are_asked_for_separately():
    found = read_status(MIXED)
    assert [one.path for one in found.staged] == ["c.txt"]
    assert sorted(one.path for one in found.unstaged) == ["a.txt", "b.txt"]


def test_a_commit_takes_what_is_staged_so_nothing_staged_is_nothing_to_commit():
    assert read_status(MIXED).can_commit
    assert not read_status("# branch.head main\n? b.txt\n").can_commit


def test_the_summary_counts_both_sides():
    assert read_status(MIXED).summary == "main — 1 staged, 2 not staged"


def test_a_clean_tree_says_so():
    found = read_status("# branch.head main\n")
    assert found.is_clean
    assert "nothing to commit" in found.summary


def test_a_file_staged_and_changed_again_is_both():
    found = read_status("# branch.head main\n1 MM N... 1 1 1 a a a.txt\n")
    assert found.changes[0].state is State.BOTH
    assert found.changes[0].is_staged


def test_a_conflict_is_neither_staged_nor_merely_changed():
    found = read_status("# branch.head main\n1 UU N... 1 1 1 a a a.txt\n")
    assert found.changes[0].state is State.CONFLICTED


def test_a_detached_head_is_known_to_be_one():
    assert read_status("# branch.head (detached)\n").detached


# --- doing things -----------------------------------------------------------


@pytest.fixture
def repository(tmp_path):
    def run(*arguments):
        subprocess.run(["git", *arguments], cwd=tmp_path, check=True, capture_output=True)

    run("init", "-q", ".")
    run("config", "user.email", "invented@example.invalid")
    run("config", "user.name", "Invented")
    (tmp_path / "a.tf").write_text('resource "terraform_data" "a" {}\n', encoding="utf-8")
    run("add", "a.tf")
    run("commit", "-qm", "first")
    return tmp_path


def test_a_real_repository_reads(repository):
    (repository / "b.tf").write_text("# new\n", encoding="utf-8")
    found = status(repository)
    assert found.branch
    assert [one.path for one in found.changes] == ["b.tf"]


def test_staging_takes_exactly_what_was_named(repository):
    """Never everything that happens to have changed."""
    (repository / "b.tf").write_text("# new\n", encoding="utf-8")
    (repository / "c.tf").write_text("# also new\n", encoding="utf-8")
    assert stage(repository, ["b.tf"]) == ""
    found = status(repository)
    assert [one.path for one in found.staged] == ["b.tf"]
    assert [one.path for one in found.unstaged] == ["c.tf"]


def test_staging_nothing_says_so_rather_than_staging_everything(repository):
    (repository / "b.tf").write_text("# new\n", encoding="utf-8")
    assert "nothing was staged" in stage(repository, []).lower()
    assert status(repository).staged == ()


def test_unstaging_puts_it_back(repository):
    (repository / "b.tf").write_text("# new\n", encoding="utf-8")
    stage(repository, ["b.tf"])
    assert unstage(repository, ["b.tf"]) == ""
    assert status(repository).staged == ()


def test_committing_what_is_staged(repository):
    (repository / "b.tf").write_text("# new\n", encoding="utf-8")
    stage(repository, ["b.tf"])
    assert commit(repository, "add b") == ""
    assert status(repository).is_clean


def test_a_commit_with_no_message_is_refused_rather_than_opening_an_editor(repository):
    assert commit(repository, "   ") == "A commit needs a message"


def test_committing_with_nothing_staged_says_what_git_said(repository):
    (repository / "b.tf").write_text("# new\n", encoding="utf-8")
    said = commit(repository, "nothing staged")
    assert said


def test_branches_are_listed_and_made_and_switched(repository):
    assert create_branch(repository, "invented-work") == ""
    assert "invented-work" in branches(repository)
    assert status(repository).branch == "invented-work"
    assert switch(repository, "-") == "" or switch(repository, branches(repository)[0]) == ""


def test_a_branch_with_no_name_is_refused(repository):
    assert create_branch(repository, "  ") == "No branch was named"
    assert switch(repository, "") == "No branch was named"


def test_pushing_with_no_remote_reads_as_a_state_rather_than_a_crash(repository):
    """Every repository somebody starts here is in this state."""
    said = push(repository)
    assert said
    assert "push destination" in said or "remote" in said.lower()


def test_a_directory_that_is_not_a_repository_says_so(tmp_path):
    found = status(tmp_path / "nowhere")
    assert found.unreadable
    assert not found.is_clean


# --- cloning ----------------------------------------------------------------


def test_a_repository_name_is_read_out_of_its_url():
    from backsight.app.window import _repository_name

    assert _repository_name("https://example.invalid/team/infrastructure.git") == "infrastructure"
    assert _repository_name("git@example.invalid:team/infrastructure.git") == "infrastructure"
    assert _repository_name("https://example.invalid/team/infrastructure/") == "infrastructure"


def test_a_url_nobody_can_read_a_name_out_of_becomes_something_renameable():
    """A folder somebody can rename, rather than a crash."""
    from backsight.app.window import _repository_name

    assert _repository_name("   ") == "repository"
    assert _repository_name("/") == "repository"


def test_cloning_nothing_is_refused(tmp_path):
    from backsight.engine.vcs.working import clone

    assert clone("   ", tmp_path / "x") == "No repository was named"


def test_a_clone_that_cannot_reach_anything_says_so_rather_than_hanging(tmp_path):
    from backsight.engine.vcs.working import clone

    said = clone("/nowhere/that/exists.git", tmp_path / "x")
    assert said
