"""Discovering tests, and refusing to touch real infrastructure by accident."""

import shutil
from pathlib import Path

import pytest

from backsight.engine.tests.execution import (
    DEFAULT_TARGET,
    NotConfirmed,
    Target,
    discover,
    run,
)
from backsight.engine.tests.results import Status

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "fixtures" / "tests" / "workspace"


def test_every_test_file_in_a_workspace_is_found(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "a.tftest.hcl").write_text("")
    (tmp_path / "b.tftest.hcl").write_text("")
    (tmp_path / "main.tf").write_text("")
    assert [p.name for p in discover(tmp_path)] == ["b.tftest.hcl", "a.tftest.hcl"]


def test_the_download_cache_is_not_searched(tmp_path):
    cache = tmp_path / ".terraform" / "modules"
    cache.mkdir(parents=True)
    (cache / "vendored.tftest.hcl").write_text("")
    assert discover(tmp_path) == []


def test_mocks_are_the_default_target():
    """Real infrastructure is never the default, and never a keybinding alone."""
    assert DEFAULT_TARGET is Target.MOCKS
    assert DEFAULT_TARGET.needs_confirmation is False


def test_only_the_real_target_costs_money():
    assert Target.REAL.costs_money is True
    assert Target.SANDBOX.costs_money is False
    assert Target.MOCKS.costs_money is False


def test_running_against_real_infrastructure_without_confirmation_is_refused(tmp_path):
    """FR-TST-06. One keystroke would otherwise bill somebody for a database."""
    with pytest.raises(NotConfirmed, match="creates and destroys real resources"):
        run(tmp_path, target=Target.REAL)


def test_the_refusal_offers_the_emulator_instead(tmp_path):
    with pytest.raises(NotConfirmed, match="emulator"):
        run(tmp_path, target=Target.REAL)


def test_every_target_explains_what_it_proves_and_what_it_costs():
    for target in Target:
        assert target.description
        assert "." in target.description


@pytest.mark.skipif(shutil.which("tofu") is None, reason="the engine binary is not installed")
def test_a_real_run_against_the_fixture_workspace(tmp_path):
    """End to end, offline: the fixture uses `terraform_data` and no provider."""
    workspace = tmp_path / "workspace"
    shutil.copytree(WORKSPACE, workspace)
    outcome = run(workspace, target=Target.MOCKS)
    assert outcome.ok, outcome.output
    assert outcome.results.passed == 1
    assert outcome.results.failed == 1
    failed = outcome.results.all_runs()[1]
    assert failed.status is Status.FAILED
    # The whole point: the values are there, from the engine.
    assert failed.failures[0].has_evidence


@pytest.mark.skipif(shutil.which("tofu") is None, reason="the engine binary is not installed")
def test_filtering_to_a_file_by_absolute_path_still_runs_it(tmp_path):
    """The engine matches a filter against the path it was given, relative to itself."""
    workspace = tmp_path / "workspace"
    shutil.copytree(WORKSPACE, workspace)
    only = discover(workspace)[0]
    assert only.is_absolute()
    outcome = run(workspace, target=Target.MOCKS, files=[only])
    # A filter that matches nothing is reported by the engine as a pass with
    # nothing run, so the count is the assertion rather than the status.
    assert outcome.results.total > 0, outcome.output
