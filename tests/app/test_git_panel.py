"""Staging and committing on screen, so nobody switches to a terminal mid-plan."""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.git_panel import NOTHING, GitPanel  # noqa: E402
from backsight.engine.vcs.working import read_status  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "git"
MIXED = read_status((FIXTURES / "status-mixed.txt").read_text(encoding="utf-8"))


def test_a_clean_tree_says_so_rather_than_showing_an_empty_list():
    panel = GitPanel()
    assert panel.branch_line == NOTHING
    assert panel.rows() == []


def test_it_lists_every_change_with_what_it_is():
    panel = GitPanel()
    panel.show(MIXED)
    said = " ".join(panel.rows())
    assert "c.txt — staged" in said
    assert "a.txt — changed" in said
    assert "b.txt — new" in said


def test_the_branch_line_counts_both_sides():
    panel = GitPanel()
    panel.show(MIXED)
    assert panel.branch_line == "main — 1 staged, 2 not staged"


def test_committing_is_only_possible_with_something_staged():
    """A commit takes what is staged, so with nothing staged there is none."""
    panel = GitPanel()
    panel.show(read_status("# branch.head main\n? b.txt\n"))
    assert not panel.can_commit
    panel.show(MIXED)
    assert panel.can_commit


def test_there_is_no_stage_everything_button():
    """Everything is rarely what anybody means and a commit is hard to take
    back."""
    panel = GitPanel()
    panel.show(MIXED)
    labels = []
    child = panel._files.get_first_child()
    while child is not None:
        button = child.get_last_child()
        labels.append(button.get_label())
        child = child.get_next_sibling()
    assert set(labels) <= {"Stage", "Unstage"}
    assert len(labels) == 3


def test_staging_one_file_names_that_file():
    staged = []
    panel = GitPanel(on_stage=staged.append)
    panel.show(MIXED)
    # `a.txt` is the changed one, so its button stages.
    for row in _rows(panel):
        if "a.txt" in getattr(row, "said", ""):
            row.get_last_child().emit("clicked")
    assert staged == [["a.txt"]]


def test_a_staged_file_offers_to_be_unstaged_instead():
    unstaged = []
    panel = GitPanel(on_unstage=unstaged.append)
    panel.show(MIXED)
    for row in _rows(panel):
        if "c.txt" in getattr(row, "said", ""):
            row.get_last_child().emit("clicked")
    assert unstaged == [["c.txt"]]


def test_a_commit_needs_a_message_and_clears_it_afterwards():
    said = []
    panel = GitPanel(on_commit=said.append)
    panel.show(MIXED)
    panel._commit()
    assert said == []
    panel.message.set_text("add the thing")
    panel._commit()
    assert said == ["add the thing"]
    assert panel.message.get_text() == ""


def test_pushing_goes_through_a_question_rather_than_the_button():
    """Outward-facing, and somebody else can pull it a second later."""
    asked = []
    panel = GitPanel(on_push=lambda: asked.append(True))
    panel.show(MIXED)
    panel._push_button.emit("clicked")
    assert asked == [True]
    assert "…" in panel._push_button.get_label()


def test_clicking_a_file_opens_it():
    opened = []
    panel = GitPanel(on_open=opened.append)
    panel.show(MIXED)
    _rows(panel)[0].get_first_child().emit("clicked")
    assert opened


def _rows(panel):
    found = []
    child = panel._files.get_first_child()
    while child is not None:
        found.append(child)
        child = child.get_next_sibling()
    return found
