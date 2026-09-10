"""The primary carries the plan's consequence, and leaves when a plan cannot run.

**It did neither.** `_run_button` was assigned and read nowhere, so the one
control that leads to committing infrastructure looked identical whether the
plan created two things or destroyed forty.
"""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.window import Window  # noqa: E402
from backsight.engine.plan.footer import Situation  # noqa: E402

WORKSPACE = Path(__file__).resolve().parents[2] / "fixtures" / "workspace"


@pytest.fixture
def window():
    return Window()


def test_a_plan_that_destroys_fills_the_control(window):
    window.mark_the_run_control(Situation(changes=3, irreversible=1))
    assert window._run_button.has_css_class("tf-irreversible")


def test_a_plan_that_only_creates_does_not(window):
    window.mark_the_run_control(Situation(changes=3, irreversible=0))
    assert not window._run_button.has_css_class("tf-irreversible")


def test_the_fill_is_dropped_again_when_the_next_plan_is_safe(window):
    window.mark_the_run_control(Situation(changes=3, irreversible=2))
    window.mark_the_run_control(Situation(changes=1, irreversible=0))
    assert not window._run_button.has_css_class("tf-irreversible")
    # A filled control that went back to quiet must look quiet again.
    assert window._run_button.has_css_class("tf-quiet")


def test_the_control_is_absent_with_nothing_open(window):
    """Absent, not disabled — a disabled control invites a press that does nothing."""
    assert window.workspace is None
    window.mark_the_run_control(Situation())
    assert not window._run_button.get_visible()


def test_a_failed_plan_keeps_the_control(window, monkeypatch):
    """*Will not run* is the workspace, not the last attempt. Retrying is the action."""
    monkeypatch.setattr(window, "_engine_found", "1.12.6")
    window.open_workspace(WORKSPACE)
    window.mark_the_run_control(Situation(errors=[object()], changes=0))
    assert window.a_plan_could_run()
    assert window._run_button.get_visible()


def test_no_engine_means_no_control(window, monkeypatch):
    monkeypatch.setattr(window, "_engine_found", "")
    window.open_workspace(WORKSPACE)
    window.mark_the_run_control(Situation())
    assert not window.a_plan_could_run()
    assert not window._run_button.get_visible()
