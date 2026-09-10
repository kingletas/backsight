"""Four states on one tab, each in its own slot, none of them lying."""

import shutil
from pathlib import Path

import pytest

from backsight.engine.insight.file_status import (
    IMPACT_PRECEDENCE,
    FileStatus,
    Impact,
    cleared_of_plan,
    for_files,
    highest,
)
from backsight.engine.insight.source_map import SourceMap
from backsight.engine.plan.model import parse
from backsight.engine.runner import process
from backsight.engine.vcs.git import Status, Vcs, read
from backsight.engine.workspace.discovery import discover

SOURCE = (
    'resource "terraform_data" "api" {\n  input = "one"\n}\n'
    '\nresource "terraform_data" "worker" {\n  input = "two"\n}\n'
)


def plan_of(*changes):
    return parse(
        {"format_version": "1.2", "terraform_version": "1.12.6", "resource_changes": list(changes)}
    )


def change(name, actions):
    return {
        "address": f"terraform_data.{name}",
        "type": "terraform_data",
        "name": name,
        "mode": "managed",
        "provider_name": "terraform.io/builtin/terraform",
        "change": {"actions": actions},
    }


@pytest.fixture
def workspace(tmp_path):
    (tmp_path / "main.tf").write_text(SOURCE)
    found = discover(tmp_path)
    return tmp_path, SourceMap.build(found, found.root_modules[0])


# --- precedence -----------------------------------------------------------


def test_one_destroy_outranks_nine_creates():
    """Ordered by consequence, not by count."""
    assert highest([Impact.CREATE] * 9 + [Impact.DESTROY]) is Impact.DESTROY


def test_the_impact_order_is_by_consequence():
    assert IMPACT_PRECEDENCE == (
        Impact.DESTROY,
        Impact.REPLACE,
        Impact.CHANGE,
        Impact.CREATE,
        Impact.UNTOUCHED,
    )


def test_a_file_the_plan_does_not_reach_is_untouched():
    assert highest([]) is Impact.UNTOUCHED


def test_destroy_is_thicker_as_well_as_the_same_colour_as_replace():
    """Both end the object, so they share a colour; weight separates them.

    The tone names differ — the theme is what maps them onto one token — so the
    check is that they resolve to the same colour rather than the same word.
    """
    # They share a consequence and not a colour: the gutter keeps replace
    # distinct because it is the change people misread most.
    from backsight.app.theme import CONSEQUENCE, PLAN_TONES

    assert CONSEQUENCE[Impact.DESTROY.tone] == CONSEQUENCE[Impact.REPLACE.tone]
    assert PLAN_TONES[Impact.DESTROY.tone] != PLAN_TONES[Impact.REPLACE.tone]
    assert Impact.DESTROY.is_thick and not Impact.REPLACE.is_thick


# --- combining the sources ------------------------------------------------


def test_a_file_carries_the_most_consequential_thing_the_plan_does_to_it(workspace):
    directory, source_map = workspace
    plan = plan_of(change("api", ["create"]), change("worker", ["delete"]))
    statuses = for_files([directory / "main.tf"], plan=plan, source_map=source_map)
    status = statuses[(directory / "main.tf").resolve()]
    assert status.impact is Impact.DESTROY
    assert status.shows_impact


def test_the_counts_are_kept_for_the_rail(workspace):
    """The rail has the width for two counts; the tab does not.

    The same four glyphs the verdict line and the gutter use — a reader should
    not have to learn that `±` here and `▲` there are the same thing."""
    directory, source_map = workspace
    plan = plan_of(change("api", ["create"]), change("worker", ["delete"]))
    status = for_files([directory / "main.tf"], plan=plan, source_map=source_map)[
        (directory / "main.tf").resolve()
    ]
    assert status.summary == "＋1 ▼1"


def test_with_no_plan_every_file_is_untouched_which_is_true(workspace):
    directory, _ = workspace
    status = for_files([directory / "main.tf"])[(directory / "main.tf").resolve()]
    assert status.impact is Impact.UNTOUCHED
    assert status.shows_impact is False


def test_an_unreadable_file_suppresses_its_plan_edge(workspace):
    """FR-ED-19e: unreadable outranks everything, and a stale edge is worse."""
    directory, source_map = workspace
    plan = plan_of(change("api", ["delete"]))
    statuses = for_files(
        [directory / "main.tf"],
        plan=plan,
        source_map=source_map,
        unreadable={directory / "main.tf"},
    )
    status = statuses[(directory / "main.tf").resolve()]
    assert status.impact is Impact.DESTROY
    assert status.shows_impact is False


def test_unsaved_is_its_own_slot_and_does_not_disturb_the_others(workspace):
    directory, source_map = workspace
    plan = plan_of(change("api", ["create"]))
    statuses = for_files(
        [directory / "main.tf"],
        plan=plan,
        source_map=source_map,
        unsaved={directory / "main.tf"},
    )
    status = statuses[(directory / "main.tf").resolve()]
    assert status.unsaved is True
    assert status.impact is Impact.CREATE


# --- staleness ------------------------------------------------------------


def test_an_edit_clears_the_plan_marker_rather_than_dimming_it():
    """A dimmed marker still reads as information, and it is no longer true."""
    before = {
        Path("a.tf"): FileStatus(
            path=Path("a.tf"),
            vcs=Vcs.MODIFIED,
            impact=Impact.DESTROY,
            unsaved=True,
            counts=((Impact.DESTROY, 1),),
        )
    }
    after = cleared_of_plan(before)[Path("a.tf")]
    assert after.impact is Impact.UNTOUCHED
    assert after.counts == ()
    # The other slots are local state and stay true.
    assert after.vcs is Vcs.MODIFIED
    assert after.unsaved is True


# --- git ------------------------------------------------------------------

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


@needs_git
def test_a_directory_that_is_not_a_repository_says_so_rather_than_failing(tmp_path):
    found = read(tmp_path)
    assert found.available is False
    assert found.files == {}


@needs_git
def test_git_states_are_read_from_a_real_repository(tmp_path):
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "T"],
    ):
        assert process.start(command, cwd=tmp_path).wait(30).ok
    (tmp_path / "tracked.tf").write_text("one\n")
    process.start(["git", "add", "tracked.tf"], cwd=tmp_path).wait(30)
    process.start(["git", "commit", "-qm", "first"], cwd=tmp_path).wait(30)

    (tmp_path / "tracked.tf").write_text("two\n")
    (tmp_path / "new.tf").write_text("three\n")
    (tmp_path / "gone.tf").write_text("four\n")
    process.start(["git", "add", "gone.tf"], cwd=tmp_path).wait(30)
    process.start(["git", "commit", "-qm", "second"], cwd=tmp_path).wait(30)
    (tmp_path / "gone.tf").unlink()

    found = read(tmp_path)
    assert found.available and not found.stale
    assert found.of(tmp_path / "tracked.tf") is Vcs.MODIFIED
    assert found.of(tmp_path / "new.tf") is Vcs.UNTRACKED
    assert found.of(tmp_path / "gone.tf") is Vcs.DELETED
    assert found.of(tmp_path / "never-existed.tf") is Vcs.UNCHANGED
    assert found.branch


@needs_git
def test_a_failed_refresh_keeps_the_previous_answer_and_marks_it_stale(tmp_path):
    """Clearing would make every tab read as unchanged, which is a claim."""
    previous = Status(files={(tmp_path / "a.tf").resolve(): Vcs.MODIFIED}, branch="main")
    found = read(tmp_path / "not-a-directory", previous=previous)
    assert found.stale is True
    assert found.of(tmp_path / "a.tf") is Vcs.MODIFIED


def test_every_git_state_has_a_letter_for_anyone_who_cannot_use_hue():
    """Letters mode is a setting, not a hidden accessibility flag."""
    for state in (Vcs.CONFLICTED, Vcs.DELETED, Vcs.MODIFIED, Vcs.UNTRACKED):
        assert state.letter
    assert Vcs.UNCHANGED.letter == ""
