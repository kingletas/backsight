"""Running a real plan, against a workspace that needs no provider or credentials.

The `terraform_data` resource is built in, so these run offline and anywhere the
engine binary exists.
"""

import shutil
from pathlib import Path

import pytest

from backsight.engine.plan.execution import speculative
from backsight.engine.plan.model import Action
from backsight.engine.runner.process import RunState

pytestmark = pytest.mark.skipif(
    shutil.which("tofu") is None, reason="the engine binary is not installed"
)


def test_the_engine_is_installed_where_the_gate_runs():
    """A skipped file reads as a passing one. CI installs the engine, so if this
    ever skips there, the workflow changed and these tests stopped running."""
    assert shutil.which("tofu") is not None


def workspace(path: Path, body: str) -> Path:
    (path / "main.tf").write_text(body)
    return path


def test_a_plan_runs_and_comes_back_as_a_model(tmp_path):
    directory = workspace(tmp_path, 'resource "terraform_data" "api" {\n  input = "one"\n}\n')
    outcome = speculative(directory)
    assert outcome.ok, outcome.output
    assert outcome.failure is None
    assert [c.action for c in outcome.plan.changes] == [Action.CREATE]
    assert outcome.plan.summary() == "1 to add"


def test_the_artifact_is_kept_so_the_reviewed_plan_is_the_applied_one(tmp_path):
    """FR-ST-03: apply what was reviewed, never a silent second plan."""
    directory = workspace(tmp_path, 'resource "terraform_data" "api" {\n  input = "one"\n}\n')
    outcome = speculative(directory)
    assert outcome.artifact is not None
    assert outcome.artifact.is_file()
    assert outcome.artifact.stat().st_size > 0


def test_configuration_that_does_not_parse_fails_with_its_own_output(tmp_path):
    directory = workspace(tmp_path, 'resource "terraform_data" {\n  oops\n')
    outcome = speculative(directory)
    assert outcome.ok is False
    assert outcome.plan is None
    assert outcome.state is RunState.FAILED
    # It used to say "the output says why" and show the output nowhere.
    assert outcome.failure
    assert "says why" not in outcome.failure
    assert outcome.output.strip(), "a failure with no output tells nobody anything"
    assert outcome.diagnostics, "the engine said something and it was not read"


def test_a_plan_that_overruns_is_reported_as_overrun_rather_than_waited_on(tmp_path):
    """Driven by a stand-in engine that just sleeps.

    Racing a real plan against a short timeout is a coin toss — the first
    version of this test lost, because the plan finished in 0.04s and the
    timeout was 0.05s. A test that sometimes passes tests nothing.
    """
    directory = workspace(tmp_path, 'resource "terraform_data" "api" {}\n')
    slow = tmp_path / "slow-engine"
    slow.write_text("#!/usr/bin/env bash\nsleep 30\n")
    slow.chmod(0o755)
    outcome = speculative(directory, timeout=0.5, engine=str(slow))
    assert outcome.ok is False
    assert outcome.state is RunState.TIMED_OUT
    assert "did not finish" in outcome.failure


def test_output_streams_while_the_plan_runs(tmp_path):
    directory = workspace(tmp_path, 'resource "terraform_data" "api" {\n  input = "one"\n}\n')
    lines: list[str] = []
    outcome = speculative(directory, on_line=lines.append)
    assert outcome.ok
    assert lines, "nothing streamed; the output panel would stay blank until the end"


def test_a_missing_engine_is_a_named_failure_and_not_a_traceback(tmp_path):
    directory = workspace(tmp_path, 'resource "terraform_data" "api" {}\n')
    with pytest.raises(FileNotFoundError):
        speculative(directory, engine="tofu-that-is-not-installed")
