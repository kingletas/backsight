"""The loop the product exists for: plan, read it, apply it, know it worked.

These run the real engine against a workspace that reaches nothing outside this
machine — no provider, no credentials, no network — so what they prove is the
whole route rather than a mock of it.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from tests.acceptance.looking import drawn, says, settle

gi = pytest.importorskip("gi", reason="the toolkit is not installed")

ROOT = Path(__file__).resolve().parents[2]
# A plan against a real engine is seconds, not milliseconds.
PATIENCE = 90


def until(window, condition, seconds: float = PATIENCE) -> bool:
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        if condition():
            return True
        settle(window, 0.25)
    return condition()


@pytest.fixture
def example(window, tmp_path):
    """The demo workspace: an add, a change, a replace and a destroy at once."""
    where = tmp_path / "example"
    shutil.copytree(ROOT / "fixtures" / "example", where)
    window.open_workspace(where)
    settle(window)
    window.open_file(where / "main.tf")
    settle(window)
    return window


def planned(window) -> bool:
    return until(window, lambda: window._plan is not None)


def test_run_plan_produces_a_plan(example):
    """It called save and relied on the save to start one, so turning off
    "plan when you save" took the button with it."""
    example.plan_now()
    assert planned(example)
    assert len(example._plan.changes) == 4


def test_the_verdict_line_fills_from_the_plan(example):
    example.plan_now()
    assert planned(example)
    settle(example, 0.5)
    assert "No plan yet" not in example._status_line.texts()


def test_the_status_bar_carries_the_counts(example):
    example.plan_now()
    assert planned(example)
    settle(example, 0.5)
    assert says(example._status_widget, "＋")


def test_the_footer_offers_what_to_do_next(example):
    example.plan_now()
    assert planned(example)
    settle(example, 0.5)
    said = example.apply_gate.action
    assert "Review" in said or "Apply" in said


def test_a_plan_that_reaches_nothing_outside_needs_no_credentials(example):
    """Requiring them always meant the one workspace that can be applied here
    could never be applied."""
    example.plan_now()
    assert planned(example)
    assert example._situation().blocked == ""


def test_applying_it_says_what_each_resource_became(example):
    example.plan_now()
    assert planned(example)
    example.run_footer_command("apply")
    assert until(example, lambda: not example._applying)
    settle(example, 0.8)
    screen = example._apply_window.screen
    assert screen.heading.startswith("Applied ")
    assert screen.said_about("terraform_data.api") == "changed"
    assert screen.said_about("terraform_data.database") == "replaced"
    assert screen.said_about("terraform_data.worker") == "created"
    assert screen.said_about("terraform_data.old_cache") == "destroyed"


def test_and_reads_the_state_back_to_check(example):
    """ "Applied" is not "working", and an exit code is not evidence."""
    example.plan_now()
    assert planned(example)
    example.run_footer_command("apply")
    assert until(example, lambda: not example._applying)
    settle(example, 0.8)
    assert "recorded in the state as the plan intended" in example._apply_window.screen.verdict


def test_the_plan_is_gone_afterwards(example):
    """A plan describes a difference that no longer exists once it is applied."""
    example.plan_now()
    assert planned(example)
    example.run_footer_command("apply")
    assert until(example, lambda: not example._applying)
    settle(example, 0.5)
    assert example._plan is None


def test_what_the_apply_printed_is_kept(example):
    from backsight.engine.plan.applying import kept_for

    example.plan_now()
    assert planned(example)
    example.run_footer_command("apply")
    assert until(example, lambda: not example._applying)
    settle(example, 0.5)
    assert kept_for(example.speculator.directory)


def test_an_apply_that_stops_part_way_says_which_of_three_things_happened(window, tmp_path):
    """The situation no other tool names."""
    where = tmp_path / "fails"
    shutil.copytree(ROOT / "fixtures" / "apply-fails", where)
    window.open_workspace(where)
    settle(window)
    window.open_file(where / "main.tf")
    settle(window)
    window.plan_now()
    assert planned(window)
    window.run_footer_command("apply")
    assert until(window, lambda: not window._applying)
    settle(window, 0.8)

    screen = window._apply_window.screen
    assert "stopped part way" in screen.heading
    assert screen.said_about("terraform_data.first") == "created"
    assert screen.said_about("terraform_data.second") == "failed"
    assert screen.said_about("terraform_data.third") == "never started"
    assert drawn(window._apply_window.screen)
