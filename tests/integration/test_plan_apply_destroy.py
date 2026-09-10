"""`plan`, `apply`, `show`, refresh and destroy — and what the emulator says.

**A green exit code is not evidence.** Every case here goes and asks S3, SQS or
DynamoDB whether the thing exists, because the whole point of an emulator is
that the answer can be checked rather than assumed.

Every command goes through the function the application calls. The direct CLI
appears twice, both times as setup or verification and never to make the thing
under test happen.
"""

from __future__ import annotations

import json

import pytest

from backsight.engine.plan import applying, commands, drifting, execution
from backsight.engine.plan.model import Action
from tests.integration import aws

pytestmark = pytest.mark.usefixtures("emulator")


def planned(workspace, **variables):
    """Init, then the application's own speculative plan."""
    commands.initialise(workspace.path, binary=workspace.engine)
    _write_variables(workspace, variables)
    return execution.speculative(workspace.path, engine=workspace.engine)


def _write_variables(workspace, variables: dict) -> None:
    if not variables:
        return
    (workspace.path / "terraform.tfvars.json").write_text(json.dumps(variables), encoding="utf-8")


def applied(workspace, **variables):
    """Plan and apply, through the application, and hand back both outcomes."""
    outcome = planned(workspace, **variables)
    assert outcome.plan is not None, outcome.failure or outcome.output
    result = applying.run(
        workspace.path,
        outcome.artifact,
        plan=outcome.plan,
        engine=workspace.engine,
    )
    assert result.ok, result.output
    return outcome, result


# --- plan -------------------------------------------------------------------


def test_plan_reads_back_what_it_would_create(workspace, named):
    outcome = planned(workspace, name=named)

    assert outcome.plan is not None, outcome.failure or outcome.output
    addresses = {change.address for change in outcome.plan.effective}
    assert addresses == {
        "aws_s3_bucket.objects",
        "aws_sqs_queue.work",
        "aws_dynamodb_table.records",
    }
    assert all(change.action is Action.CREATE for change in outcome.plan.effective)


def test_the_artifact_is_written_where_the_apply_will_look_for_it(workspace, named):
    """Applying the artifact rather than the configuration is the promise: what
    runs is what was reviewed."""
    outcome = planned(workspace, name=named)
    assert outcome.artifact is not None
    assert outcome.artifact.is_file()


@pytest.mark.fixture_name("invalid")
def test_a_plan_that_cannot_run_says_why_and_produces_nothing(workspace):
    commands.initialise(workspace.path, binary=workspace.engine)
    outcome = execution.speculative(workspace.path, engine=workspace.engine)

    assert outcome.plan is None
    assert outcome.errors or outcome.failure, "it failed without saying anything"


def test_planning_an_applied_configuration_again_finds_nothing_to_do(workspace, named):
    """The quiet case, and the one people check least: a second plan over
    infrastructure that already matches must be empty."""
    applied(workspace, name=named)
    again = planned(workspace, name=named)

    assert again.plan is not None, again.failure
    assert not again.plan.effective, [c.address for c in again.plan.effective]


# --- apply, and whether it happened -----------------------------------------


def test_apply_creates_what_the_plan_said_and_the_emulator_agrees(workspace, named):
    """**The case this whole environment exists for.** Terraform said it made
    three things; three services are asked whether it did."""
    applied(workspace, name=named)

    assert f"{named}-objects" in aws.buckets(workspace.endpoint)
    assert f"{named}-work" in aws.queues(workspace.endpoint)
    assert f"{named}-records" in aws.tables(workspace.endpoint)


def test_apply_reports_each_resource_as_it_moves(workspace, named):
    _outcome, result = applied(workspace, name=named)

    assert result.progress.finished
    assert result.progress.done == 3
    assert not result.progress.is_partial


def test_an_update_reaches_the_service_and_not_only_the_state(workspace, named):
    """Changing a variable and applying again. The queue is asked what its own
    delay is, because state agreeing with itself proves nothing."""
    applied(workspace, name=named)
    outcome, _result = applied(workspace, name=named, queue_delay=45)

    changed = [c for c in outcome.plan.effective if c.action is Action.UPDATE]
    assert [c.address for c in changed] == ["aws_sqs_queue.work"]

    url = _queue_url(workspace, named)
    assert aws.queue_delay(workspace.endpoint, url) == 45


def _queue_url(workspace, named: str) -> str:
    said = aws.client("sqs", workspace.endpoint).get_queue_url(QueueName=f"{named}-work")
    return said["QueueUrl"]


# --- show, and the state the application reads ------------------------------


def test_the_state_the_application_reads_names_what_was_created(workspace, named):
    """`show -json` through `commands.state`, which is what the Show state
    command runs."""
    applied(workspace, name=named)
    said = commands.state(workspace.path, binary=workspace.engine)

    assert not said.empty_because, said.empty_because
    assert "aws_s3_bucket.objects" in said.resources
    assert "aws_sqs_queue.work" in said.resources


def test_the_state_of_a_workspace_with_nothing_in_it_says_so(workspace):
    """Empty is a state rather than an error, and it must not read as one."""
    commands.initialise(workspace.path, binary=workspace.engine)
    said = commands.state(workspace.path, binary=workspace.engine)
    assert said.is_empty
    assert said.summary(), "an empty state said nothing at all"


@pytest.mark.fixture_name("outputs")
def test_outputs_come_back_out_of_the_state_with_their_types(workspace):
    """The application reads outputs out of `show -json` rather than running
    `output`, so this is where an output is proved to arrive."""
    commands.initialise(workspace.path, binary=workspace.engine)
    workspace.run("apply", "-auto-approve", "-input=false", "-no-color")
    said = commands.state(workspace.path, binary=workspace.engine)
    document = json.loads(said.output)
    outputs = {name: one["value"] for name, one in document["values"]["outputs"].items()}

    assert outputs["environment"] == "integration"
    assert outputs["a_number"] == 42
    assert outputs["a_list"] == ["one", "two"]
    assert outputs["marker"] == "marked-integration"


# --- refresh, which the application does as a refresh-only plan --------------


def test_a_change_made_outside_terraform_is_found_by_a_drift_check(workspace, named):
    """**Changed behind Terraform's back, then found.** The queue's delay is set
    through the API, and the application's drift check is asked what moved."""
    applied(workspace, name=named)
    aws.set_queue_delay(workspace.endpoint, _queue_url(workspace, named), 90)

    found = drifting.check(workspace.path, engine=workspace.engine)

    assert found.checked, found.headline
    assert found.count >= 1, found.headline
    assert any("aws_sqs_queue.work" in one.address for one in found.resources)


@pytest.mark.fixture_name("outputs")
def test_a_drift_check_over_untouched_infrastructure_finds_nothing(workspace):
    """The quiet half. A checker that has only ever been seen firing has not
    been tested, and the clean shape is not the drifted shape with an empty
    list in it.

    **On `terraform_data`, not on the AWS fixture**, and that is a measurement
    rather than a convenience: the AWS provider reports `tags: null → {}` on
    every resource it reads back from this emulator, so a refresh over
    untouched AWS infrastructure here is *never* empty. That is the provider
    and the emulator disagreeing about an unset map, not the application
    finding drift — and a quiet case that can never be quiet proves nothing.
    """
    commands.initialise(workspace.path, binary=workspace.engine)
    workspace.run("apply", "-auto-approve", "-input=false", "-no-color")

    found = drifting.check(workspace.path, engine=workspace.engine)

    assert found.checked, found.headline
    assert found.count == 0, found.headline


def test_the_aws_provider_reports_an_unset_tag_map_as_a_difference(workspace, named):
    """**Named rather than worked around.** Every AWS resource read back from
    this emulator differs by `tags: null → {}`, so anything asserting an empty
    refresh against them would be asserting the emulator's behaviour rather
    than the application's. Written down here so the next person meets it as a
    known thing rather than as a mystery."""
    applied(workspace, name=named)
    found = drifting.check(workspace.path, engine=workspace.engine)

    assert found.checked
    differences = {one.name for res in found.resources for one in res.differences}
    assert differences == {"tags"}, differences


def test_a_drift_check_changes_nothing(workspace, named):
    """Read-only by construction is the reason it can be run without asking."""
    applied(workspace, name=named)
    before = aws.buckets(workspace.endpoint)
    drifting.check(workspace.path, engine=workspace.engine)
    assert aws.buckets(workspace.endpoint) == before


# --- destroy ----------------------------------------------------------------


def test_destroying_removes_the_objects_from_the_emulator(workspace, named):
    """The application never runs `destroy`: destruction is applying a plan
    that destroys, which is what this drives — and then the services are asked
    whether the objects are gone."""
    applied(workspace, name=named)
    assert f"{named}-objects" in aws.buckets(workspace.endpoint)

    _remove_the_resources(workspace)
    outcome = planned(workspace, name=named)
    assert outcome.plan is not None, outcome.failure
    assert all(c.action is Action.DELETE for c in outcome.plan.effective)

    result = applying.run(
        workspace.path, outcome.artifact, plan=outcome.plan, engine=workspace.engine
    )
    assert result.ok, result.output

    assert f"{named}-objects" not in aws.buckets(workspace.endpoint)
    assert f"{named}-work" not in aws.queues(workspace.endpoint)
    assert f"{named}-records" not in aws.tables(workspace.endpoint)


def _remove_the_resources(workspace) -> None:
    """Takes the resources out of the configuration, which is what makes the
    next plan a destroy.

    **And the outputs with them.** An output referring to a resource that is no
    longer declared is a configuration that will not plan at all, so removing
    half of it produced a parse failure rather than a destroy — which is a real
    thing to get wrong and worth the extra line.
    """
    said = (workspace.path / "main.tf").read_text(encoding="utf-8")
    (workspace.path / "main.tf").write_text(
        said[: said.index('data "aws_caller_identity"')], encoding="utf-8"
    )
    (workspace.path / "outputs.tf").unlink()
