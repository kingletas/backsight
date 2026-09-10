"""`console`, `test` and `version` — the three the other files do not reach.

`console` and `test` both run the engine against a real configuration, so they
belong here rather than in the unit suite where they can only be run against a
fake. `version` is the one command the application runs with no workspace at
all, and it is what decides whether the engine is there.
"""

from __future__ import annotations

import pytest

from backsight.engine.console import evaluation
from backsight.engine.plan import commands
from backsight.engine.runner import process
from backsight.engine.tests import execution as test_execution
from backsight.engine.tests.execution import Target
from backsight.engine.tests.results import Status

pytestmark = pytest.mark.usefixtures("emulator")


# --- console ----------------------------------------------------------------


@pytest.mark.fixture_name("outputs")
def test_the_console_evaluates_an_expression_against_the_workspace(workspace):
    commands.initialise(workspace.path, binary=workspace.engine)
    said = evaluation.evaluate(workspace.path, "1 + 1", binary=workspace.engine)

    assert said.failure is None, said.failure
    assert said.value == "2"


@pytest.mark.fixture_name("outputs")
def test_it_reads_a_variable_the_configuration_declares(workspace):
    """Which is the whole reason it runs in the workspace rather than anywhere."""
    commands.initialise(workspace.path, binary=workspace.engine)
    said = evaluation.evaluate(workspace.path, "var.environment", binary=workspace.engine)

    assert said.failure is None, said.failure
    assert "integration" in said.value


@pytest.mark.fixture_name("outputs")
def test_an_expression_that_will_not_evaluate_says_what_is_wrong(workspace):
    commands.initialise(workspace.path, binary=workspace.engine)
    said = evaluation.evaluate(workspace.path, "var.not_a_variable", binary=workspace.engine)

    assert said.failure is not None
    assert said.failure.summary


def test_an_empty_expression_is_refused_without_starting_anything(workspace):
    """Refused here rather than by spawning a process to be told the same thing
    more slowly."""
    said = evaluation.evaluate(workspace.path, "   ", binary=workspace.engine)
    assert said.failure is not None
    assert said.failure.summary == "Nothing to evaluate"


# --- test -------------------------------------------------------------------


@pytest.mark.fixture_name("tests")
def test_the_runner_finds_the_test_files_the_way_the_tree_shows_them(workspace):
    found = test_execution.discover(workspace.path)
    assert [one.name for one in found] == ["failing.tftest.hcl", "passing.tftest.hcl"]


@pytest.mark.fixture_name("tests")
def test_a_passing_run_reports_each_assertion_as_passed(workspace):
    commands.initialise(workspace.path, binary=workspace.engine)
    outcome = test_execution.run(
        workspace.path,
        files=[workspace.path / "passing.tftest.hcl"],
        target=Target.MOCKS,
        engine=workspace.engine,
    )

    assert outcome.ok, outcome.output
    assert outcome.results.total == 2
    assert outcome.results.passed == 2
    assert outcome.results.failed == 0


@pytest.mark.fixture_name("tests")
def test_a_failing_run_is_reported_as_failing_rather_than_as_nothing(workspace):
    """**The half that matters.** A runner that has only ever been seen passing
    has not been tested, and a failure read as an empty result is worse than a
    crash."""
    commands.initialise(workspace.path, binary=workspace.engine)
    outcome = test_execution.run(
        workspace.path,
        files=[workspace.path / "failing.tftest.hcl"],
        target=Target.MOCKS,
        engine=workspace.engine,
    )

    # The command ran, so the run itself succeeded. What must not happen is the
    # failure arriving as an empty result.
    assert outcome.ok
    assert outcome.results.status is Status.FAILED
    assert outcome.results.failed == 1
    assert outcome.results.passed == 0


@pytest.mark.fixture_name("tests")
def test_a_failure_says_which_assertion_and_what_it_expected(workspace):
    commands.initialise(workspace.path, binary=workspace.engine)
    outcome = test_execution.run(
        workspace.path,
        files=[workspace.path / "failing.tftest.hcl"],
        target=Target.MOCKS,
        engine=workspace.engine,
    )

    failures = [one for run in outcome.results.all_runs() for one in run.failures]
    assert failures, outcome.output
    assert any("Deliberate" in one.summary + one.detail for one in failures)
    # The evidence is the point: the engine says what the expression actually was.
    assert any(one.has_evidence for one in failures), outcome.output


@pytest.mark.fixture_name("tests")
def test_running_against_a_real_account_is_refused_without_being_confirmed(workspace):
    """`confirmed` is a parameter rather than a setting, so touching real
    infrastructure is a decision taken at the moment it happens."""
    with pytest.raises(test_execution.NotConfirmed):
        test_execution.run(
            workspace.path, target=Target.REAL, engine=workspace.engine, confirmed=False
        )


# --- version ----------------------------------------------------------------


def test_the_engine_says_which_version_it_is(workspace):
    """The one command the application runs with no workspace, and what decides
    whether there is an engine at all."""
    said = process.capture([workspace.engine, "version", "-json"], cwd=workspace.path, timeout=10.0)
    assert said.ok, said.err
    assert '"terraform_version"' in said.out
