"""Standing a configuration up against the emulator, and never overclaiming.

The two properties that matter: a user's files are never touched, and a partial
result never wears the clothes of a pass.
"""

import gzip
import json
import os
from pathlib import Path

import pytest

from backsight.engine.sandbox.convergence import (
    DEFAULT_THRESHOLD,
    FORBIDDEN_WORDS,
    Coverage,
    Outcome,
    Result,
    converge,
)
from backsight.engine.sandbox.ministack import Sandbox
from backsight.engine.sandbox.override import (
    OVERRIDE_FILE,
    override_hcl,
    prepare,
    services_from_schema,
)
from backsight.engine.sandbox.runtime import detect
from backsight.engine.schema.index import SchemaIndex, build

ROOT = Path(__file__).resolve().parents[2]
CONVERGE = ROOT / "fixtures" / "converge"
UGLY = ROOT / "fixtures" / "hcl" / "ugly"
VERSIONS = {
    "registry.opentofu.org/hashicorp/aws": "5.82.2",
    "registry.opentofu.org/hashicorp/local": "2.5.2",
    "registry.opentofu.org/hashicorp/null": "3.2.3",
    "registry.opentofu.org/hashicorp/random": "3.6.3",
}
needs_runtime = pytest.mark.skipif(detect() is None, reason="no container runtime installed")
# Marked as well as skipped: `make check` leaves these out for time, `make ci`
# runs them. A skip is about the machine; the marker is about the wait.
sandbox_test = pytest.mark.sandbox


@pytest.fixture(scope="module")
def services(tmp_path_factory):
    with gzip.open(ROOT / "fixtures" / "schema" / "providers-schema.json.gz", "rt") as handle:
        schema = json.load(handle)
    database = tmp_path_factory.mktemp("converge-schema") / "schema.db"
    build(schema, database, VERSIONS)
    with SchemaIndex(database) as index:
        return services_from_schema(index)


# --- the override ---------------------------------------------------------


def test_every_endpoint_the_provider_declares_is_redirected(services):
    """A service left pointing at the real cloud would reach a real account."""
    assert len(services) > 250
    written = override_hcl("http://127.0.0.1:14566", services)
    for name in ("s3", "ec2", "dynamodb", "sqs", "quicksight"):
        assert f"{name} " in written or f"{name}=" in written
    assert written.count("http://127.0.0.1:14566") == len(services)


def test_an_override_with_no_endpoints_is_refused():
    with pytest.raises(ValueError, match="would reach the real cloud"):
        override_hcl("http://127.0.0.1:14566", [])


def test_the_override_disables_every_credential_lookup(services):
    written = override_hcl("http://127.0.0.1:14566", services)
    for flag in (
        "skip_credentials_validation",
        "skip_metadata_api_check",
        "skip_requesting_account_id",
        "skip_region_validation",
    ):
        assert f"{flag}" in written


def test_preparing_a_run_copies_rather_than_edits(tmp_path, services):
    """FR-SIM-02 and DD-9. The override lives in the copy, never in the workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "main.tf").write_text('resource "aws_s3_bucket" "a" {\n  bucket = "b"\n}\n')
    before = (workspace / "main.tf").read_bytes()

    scratch = tmp_path / "scratch"
    prepare(workspace, scratch, endpoint="http://127.0.0.1:1", services=services)

    assert (workspace / "main.tf").read_bytes() == before
    assert not (workspace / OVERRIDE_FILE).exists(), "the override was written into the workspace"
    assert (scratch / OVERRIDE_FILE).is_file()
    assert (scratch / "main.tf").read_bytes() == before


def test_the_round_trip_corpus_is_untouched_by_preparing_a_run(tmp_path, services):
    """The convergence acceptance test: any mutation of a user file fails the task."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for path in sorted(UGLY.glob("*.tf")):
        (workspace / path.name).write_bytes(path.read_bytes())
    before = {p.name: p.read_bytes() for p in workspace.glob("*.tf")}

    prepare(workspace, tmp_path / "scratch", endpoint="http://127.0.0.1:1", services=services)

    assert {p.name: p.read_bytes() for p in workspace.glob("*.tf")} == before


# --- what the result is allowed to say ------------------------------------


def test_a_partial_result_never_reads_as_a_pass():
    """FR-SIM-05. Partial gets its own weight and its own word."""
    partial = Result(outcome=Outcome.PARTIAL, coverage=Coverage(attempted=4, converged=3))
    assert partial.outcome.is_pass is False
    assert partial.headline.startswith("Partial")
    assert "Passed" not in partial.headline


def test_a_pass_still_states_its_coverage():
    passed = Result(outcome=Outcome.CONVERGED, coverage=Coverage(attempted=4, converged=4))
    assert passed.headline == "Passed · 100% coverage"


def test_the_disclaimer_is_part_of_every_result():
    """FR-SIM-06. Permanent interface text, because people forget onboarding."""
    said = Result(outcome=Outcome.CONVERGED, coverage=Coverage(1, 1)).disclaimer
    assert "does not predict what will happen in your account" in said


def test_no_result_wording_claims_to_predict_anything():
    """The headline and the reason are claims. The disclaimer is a denial.

    An earlier version of this checked the disclaimer too and failed on its own
    wording — "does not predict what will happen" contains the phrase it forbids.
    A rule that cannot tell a claim from its denial is not the rule wanted here.
    """
    for outcome in Outcome:
        result = Result(outcome=outcome, coverage=Coverage(4, 3), uncovered=("a.b",))
        claims = f"{result.headline} {result.reason}".lower()
        for forbidden in FORBIDDEN_WORDS:
            assert forbidden not in claims


def test_the_disclaimer_denies_the_claim_rather_than_avoiding_the_words():
    said = Result(outcome=Outcome.CONVERGED, coverage=Coverage(1, 1)).disclaimer.lower()
    assert "does not predict" in said
    assert "applies cleanly" in said


def test_coverage_is_a_fraction_of_what_was_attempted():
    assert Coverage(attempted=4, converged=3).percent == 75
    assert Coverage(attempted=0, converged=0).percent == 0
    assert Coverage(attempted=4, converged=3).meets(DEFAULT_THRESHOLD) is False
    assert Coverage(attempted=5, converged=4).meets(DEFAULT_THRESHOLD) is True


def test_a_sandbox_that_is_not_running_is_unavailable_rather_than_failed(tmp_path, services):
    """Not run and failed are different things, and only one is the user's problem."""
    sandbox = Sandbox(runtime=detect() or None, port=1, name="nothing") if detect() else None
    if sandbox is None:
        pytest.skip("no container runtime installed")
    result = converge(
        CONVERGE / "supported", sandbox, services=services, scratch=tmp_path / "scratch"
    )
    assert result.outcome is Outcome.UNAVAILABLE
    assert result.headline == "Not run"


# --- against a real emulator ----------------------------------------------


@pytest.fixture(scope="module")
def sandbox(tmp_path_factory):
    # One provider download shared by every run here, rather than one each.
    os.environ["TF_PLUGIN_CACHE_DIR"] = str(tmp_path_factory.mktemp("plugins"))
    # Named and ported per process: two suites on one machine must not share a
    # container, and the first one to finish must not remove the other's.
    made = Sandbox(name=f"backsight-converge-test-{os.getpid()}", port=14581 + os.getpid() % 300)
    made.start()
    made.wait_until_healthy()
    yield made
    made.stop()


@needs_runtime
@sandbox_test
def test_a_supported_configuration_converges(sandbox, services, tmp_path):
    result = converge(CONVERGE / "supported", sandbox, services=services, scratch=tmp_path / "run")
    assert result.outcome is Outcome.CONVERGED, result.output[-800:]
    assert result.coverage.attempted == 3
    assert result.uncovered == ()
    assert result.emulator_version


@needs_runtime
@sandbox_test
def test_a_resource_the_emulator_cannot_stand_up_makes_the_run_partial(sandbox, services, tmp_path):
    result = converge(CONVERGE / "mixed", sandbox, services=services, scratch=tmp_path / "run")
    assert result.outcome is Outcome.PARTIAL
    assert result.outcome.is_pass is False
    assert "aws_quicksight_group.analysts" in result.uncovered
    # FR-SIM-05: name what was not covered. A percentage tells nobody which risk.
    assert "aws_quicksight_group.analysts" in result.reason


@needs_runtime
@sandbox_test
def test_a_convergence_run_leaves_the_workspace_byte_identical(sandbox, services, tmp_path):
    before = {p.name: p.read_bytes() for p in (CONVERGE / "supported").glob("*.tf")}
    converge(CONVERGE / "supported", sandbox, services=services, scratch=tmp_path / "run")
    assert {p.name: p.read_bytes() for p in (CONVERGE / "supported").glob("*.tf")} == before
