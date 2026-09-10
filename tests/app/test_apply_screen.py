"""The screen that does not go quiet at the moment anxiety peaks.

Every Terraform tool logs an apply and stops. What a person needs is the list
they already reviewed, ticking over, and then one of three endings said in words
rather than an exit code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.apply_screen import NOTHING, STOPPED, ApplyScreen  # noqa: E402
from backsight.engine.plan.applying import Progress, Stage, follow, steps_for  # noqa: E402
from backsight.engine.plan.model import Action, Plan, ResourceChange  # noqa: E402
from backsight.engine.plan.verifying import Verification, verify  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def a_plan(*pairs) -> Plan:
    return Plan(
        format_version="1.2",
        engine_version="1.12.6",
        changes=tuple(
            ResourceChange(a, a.split(".")[0], a.split(".")[-1], "managed", "terraform", action)
            for a, action in pairs
        ),
    )


def lines(name: str) -> list[str]:
    return (FIXTURES / "apply" / name).read_text(encoding="utf-8").splitlines()


THE_FOUR = a_plan(
    ("terraform_data.api", Action.UPDATE),
    ("terraform_data.database", Action.REPLACE),
    ("terraform_data.worker", Action.CREATE),
    ("terraform_data.old_cache", Action.DELETE),
)

THE_CHAIN = a_plan(
    ("terraform_data.first", Action.CREATE),
    ("terraform_data.second", Action.CREATE),
    ("terraform_data.third", Action.CREATE),
)


def test_it_opens_on_the_plan_that_was_reviewed():
    screen = ApplyScreen()
    screen.begin(Progress(steps=steps_for(THE_FOUR)), where="prod")
    assert "Applying 4 changes to prod" == screen.heading
    assert screen.said_about("terraform_data.api") == "waiting"


def test_each_resource_is_named_by_what_became_of_it():
    """ "Done" says nothing about whether a thing was made or removed."""
    screen = ApplyScreen()
    progress = follow(THE_FOUR, lines("succeeded.jsonl"))
    screen.begin(progress)
    screen.finished(progress)
    assert screen.said_about("terraform_data.api") == "changed"
    assert screen.said_about("terraform_data.database") == "replaced"
    assert screen.said_about("terraform_data.worker") == "created"
    assert screen.said_about("terraform_data.old_cache") == "destroyed"


def test_a_finished_apply_says_how_many_and_what_the_state_agrees_with():
    screen = ApplyScreen()
    progress = follow(THE_FOUR, lines("succeeded.jsonl"))
    screen.begin(progress)
    screen.finished(progress, Verification(checks=()))
    assert screen.heading == "Applied 4 changes"


def test_stopping_part_way_says_so_in_those_words():
    """The situation no other tool names, and the one somebody most needs
    described rather than logged."""
    screen = ApplyScreen()
    progress = follow(THE_CHAIN, lines("failed-part-way.jsonl"))
    screen.begin(progress)
    screen.finished(progress)
    assert screen.heading == STOPPED
    assert screen.said_about("terraform_data.first") == "created"
    assert screen.said_about("terraform_data.second") == "failed"
    assert screen.said_about("terraform_data.third") == "never started"


def test_an_apply_that_reached_nothing_says_nothing_changed():
    """The engine failed before it touched anything — a bad backend, a lock
    held elsewhere. Nothing to reconcile, and saying so is worth more than a
    stack trace."""
    screen = ApplyScreen()
    progress = Progress(steps=steps_for(THE_CHAIN))
    progress.failure = "Error: Backend initialization required"
    for step in progress.steps:
        step.stage = Stage.NEVER_REACHED
    screen.begin(progress)
    screen.finished(progress)
    assert screen.heading == NOTHING
    assert not progress.is_partial


def test_one_resource_failing_is_already_a_partial_apply():
    """A create that errors may have made the object and marked it tainted, so
    the workspace matches neither the before nor the after."""
    screen = ApplyScreen()
    progress = Progress(steps=steps_for(a_plan(("terraform_data.only", Action.CREATE))))
    progress.steps[0].stage = Stage.FAILED
    progress.failure = "it errored"
    screen.begin(progress)
    screen.finished(progress)
    assert screen.heading == STOPPED


def test_the_verdict_carries_the_failure_and_what_the_state_says():
    screen = ApplyScreen()
    progress = follow(THE_CHAIN, lines("failed-part-way.jsonl"))
    screen.begin(progress)
    screen.finished(progress, verify(THE_CHAIN, Path("/nowhere")))
    assert "errored" in screen.verdict.lower()
    assert "could not be read back" in screen.verdict


def test_nothing_is_claimed_before_the_apply_has_ended():
    """A verdict with nothing behind it is the claim this must never make."""
    screen = ApplyScreen()
    screen.begin(Progress(steps=steps_for(THE_FOUR)))
    assert screen.verdict == ""


def test_the_bar_says_how_much_happened_rather_than_how_much_was_tried():
    """A full bar over "stopped part way" is the screen contradicting its own
    headline."""
    screen = ApplyScreen()
    progress = follow(THE_CHAIN, lines("failed-part-way.jsonl"))
    screen.begin(progress)
    screen.finished(progress)
    assert screen._bar.get_fraction() == pytest.approx(1 / 3)
    assert "tf-bar-stopped" in screen._bar.get_css_classes()


def test_a_finished_apply_fills_it():
    screen = ApplyScreen()
    progress = follow(THE_FOUR, lines("succeeded.jsonl"))
    screen.begin(progress)
    screen.finished(progress)
    assert screen._bar.get_fraction() == pytest.approx(1.0)
    assert "tf-bar-stopped" not in screen._bar.get_css_classes()
