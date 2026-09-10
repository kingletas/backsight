"""The file tree: one level at a time, and nothing below it until it is asked for.

Every rule here is one of the acceptance criteria for the rail. They are stated
as what is **not** read, because that is what makes a repository of any size
affordable and what makes the rail a place you navigate rather than a dump.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backsight.engine.layout.tree import HIDDEN, ancestors, children, has_children, matching


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A repository shaped like a real one, three levels deep."""
    for where in (
        "examples/network-hub",
        "examples/data-pipeline",
        "modules/context",
        "modules/iam-role",
        ".github/workflows",
        "docs",
        ".git/objects",
    ):
        (tmp_path / where).mkdir(parents=True)
    for name in ("README.md", "Makefile", ".gitignore", ".tflint.hcl", "CHANGELOG.md"):
        (tmp_path / name).write_text("", encoding="utf-8")
    for module in ("examples/network-hub", "examples/data-pipeline", "modules/context"):
        for name in ("main.tf", "outputs.tf", "variables.tf"):
            (tmp_path / module / name).write_text("", encoding="utf-8")
    (tmp_path / ".git" / "objects" / "pack").write_text("", encoding="utf-8")
    return tmp_path


# --- one level -------------------------------------------------------------


def test_the_root_shows_its_immediate_children_and_nothing_below_them(repository):
    said = [entry.shown for entry in children(repository)]
    assert said == [
        ".github/",
        "docs/",
        "examples/",
        "modules/",
        ".gitignore",
        ".tflint.hcl",
        "CHANGELOG.md",
        "Makefile",
        "README.md",
    ]


def test_directories_come_before_files(repository):
    kinds = [entry.is_dir for entry in children(repository)]
    assert kinds == sorted(kinds, reverse=True)


def test_each_group_is_alphabetical_whatever_case_it_is_in(repository):
    files = [entry.name for entry in children(repository) if not entry.is_dir]
    assert files == sorted(files, key=str.casefold)


def test_opening_a_directory_reveals_its_children_and_leaves_them_closed(repository):
    """The key behavioural rule: expanding is one level, never a recursion."""
    said = [entry.shown for entry in children(repository / "examples")]
    assert said == ["data-pipeline/", "network-hub/"]


def test_a_files_names_are_only_read_when_its_directory_is(repository):
    """A file is never in the tree because its directory exists somewhere."""
    everything = [entry.name for entry in children(repository)]
    assert "main.tf" not in everything


# --- what is hidden, and what is not --------------------------------------


def test_git_and_terraform_machinery_are_hidden(repository):
    assert ".git" not in [entry.name for entry in children(repository)]
    assert ".git" in HIDDEN and ".terraform" in HIDDEN


def test_every_other_dotfile_stays(repository):
    """`.tflint.hcl` and `.gitignore` are as much a part of an infrastructure
    repository as its `.tf` files, and hiding them because a file manager would
    is a convention borrowed from the wrong application."""
    said = [entry.name for entry in children(repository)]
    assert ".gitignore" in said
    assert ".tflint.hcl" in said
    assert ".github" in said


def test_a_directory_that_cannot_be_read_is_empty_rather_than_an_error(tmp_path):
    assert children(tmp_path / "nothing-here") == []


# --- what a chevron is offered for ----------------------------------------


def test_an_empty_directory_offers_nothing_to_open(tmp_path):
    (tmp_path / "empty").mkdir()
    assert has_children(tmp_path / "empty") is False


def test_a_directory_with_something_in_it_does(repository):
    assert has_children(repository / "examples") is True


# --- revealing -------------------------------------------------------------


def test_revealing_a_file_names_only_its_own_ancestors(repository):
    found = ancestors(repository / "modules" / "context" / "main.tf", repository)
    assert [path.name for path in found] == ["modules", "context"]


def test_a_file_at_the_root_has_no_ancestors_to_open(repository):
    assert ancestors(repository / "README.md", repository) == []


def test_something_outside_the_workspace_reveals_nothing(repository, tmp_path):
    assert ancestors(tmp_path.parent / "elsewhere.tf", repository) == []


# --- filtering -------------------------------------------------------------


def test_a_filter_finds_files_anywhere_in_the_tree(repository):
    found = matching(repository, "outputs")
    assert len(found) == 3
    assert all(path.name == "outputs.tf" for path in found)


def test_it_matches_part_of_a_name_and_ignores_case(repository):
    assert matching(repository, "MAIN")


def test_it_returns_files_rather_than_the_folders_on_the_way(repository):
    assert all(path.is_file() for path in matching(repository, "main"))


def test_an_empty_filter_finds_nothing_rather_than_everything(repository):
    assert matching(repository, "   ") == []


def test_it_stops_rather_than_walking_a_repository_of_any_size(repository):
    """A filter that reads a hundred thousand files to answer a three-letter
    question is one people learn not to type in."""
    assert matching(repository, "tf", limit=2) == matching(repository, "tf", limit=2)
    assert len(matching(repository, "main", limit=1)) <= 1
