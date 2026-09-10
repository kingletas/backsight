"""Reading a real apply stream, resource by resource, against the reviewed plan.

Both streams here are captures of applies that actually ran — see
`fixtures/PROVENANCE.md`. The interleaving is the reason: `tofu` does not report
in the plan's order, and a replace arrives as a destroy early and a create much
later, with other resources between them.
"""

from __future__ import annotations

import json
from pathlib import Path

from backsight.engine.plan.applying import (
    Progress,
    Stage,
    follow,
    read_events,
    steps_for,
)
from backsight.engine.plan.execution import parse
from backsight.engine.plan.model import Action, Plan, ResourceChange

FIXTURES = Path(__file__).resolve().parents[1].parent / "fixtures" / "apply"


def a_plan(*addresses_and_actions) -> Plan:
    return Plan(
        format_version="1.2",
        engine_version="1.12.6",
        changes=tuple(
            ResourceChange(
                address=address,
                type=address.split(".")[0],
                name=address.split(".")[-1],
                mode="managed",
                provider="terraform",
                action=action,
            )
            for address, action in addresses_and_actions
        ),
    )


def lines(name: str) -> list[str]:
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


# --- the successful apply --------------------------------------------------


def test_the_whole_plan_finishes_and_says_what_each_one_became():
    plan = a_plan(
        ("terraform_data.api", Action.UPDATE),
        ("terraform_data.database", Action.REPLACE),
        ("terraform_data.worker", Action.CREATE),
        ("terraform_data.old_cache", Action.DELETE),
    )
    progress = follow(plan, lines("succeeded.jsonl"))
    assert progress.finished
    assert progress.ok
    assert progress.done == 4
    words = {step.address: step.word for step in progress.steps}
    assert words["terraform_data.api"] == "changed"
    assert words["terraform_data.database"] == "replaced"
    assert words["terraform_data.worker"] == "created"
    assert words["terraform_data.old_cache"] == "destroyed"


def test_a_replacement_is_not_done_when_only_its_destroy_has_finished():
    """The destroy arrives early and the create much later. Marking it done at
    the destroy would tell somebody the new one exists while it does not."""
    plan = a_plan(("terraform_data.database", Action.REPLACE))
    progress = Progress(steps=steps_for(plan))
    from backsight.engine.plan.applying import apply_event

    seen = list(read_events(lines("succeeded.jsonl")))
    for event in seen:
        apply_event(progress, event)
        if "Destruction complete" in str(event.get("@message", "")):
            break
    assert progress.steps[0].stage is Stage.RUNNING


def test_the_order_shown_is_the_order_that_was_reviewed():
    """`tofu` reports as it goes. The person read a list and it must not
    reshuffle itself while they watch."""
    plan = a_plan(
        ("terraform_data.api", Action.UPDATE),
        ("terraform_data.database", Action.REPLACE),
        ("terraform_data.worker", Action.CREATE),
        ("terraform_data.old_cache", Action.DELETE),
    )
    progress = follow(plan, lines("succeeded.jsonl"))
    assert [step.address for step in progress.steps] == [
        "terraform_data.api",
        "terraform_data.database",
        "terraform_data.worker",
        "terraform_data.old_cache",
    ]


def test_a_no_op_is_never_a_step():
    plan = a_plan(("terraform_data.same", Action.NO_OP), ("terraform_data.api", Action.UPDATE))
    assert [step.address for step in steps_for(plan)] == ["terraform_data.api"]


# --- the apply that stopped part way ---------------------------------------


def test_a_failed_apply_separates_what_happened_from_what_never_started():
    """Three situations, not two: changed, failed, and never attempted."""
    plan = a_plan(
        ("terraform_data.first", Action.CREATE),
        ("terraform_data.second", Action.CREATE),
        ("terraform_data.third", Action.CREATE),
    )
    progress = follow(plan, lines("failed-part-way.jsonl"))
    stages = {step.address: step.stage for step in progress.steps}
    assert stages["terraform_data.first"] is Stage.DONE
    assert stages["terraform_data.second"] is Stage.FAILED
    assert stages["terraform_data.third"] is Stage.NEVER_REACHED


def test_it_knows_the_apply_was_partial():
    plan = a_plan(
        ("terraform_data.first", Action.CREATE),
        ("terraform_data.second", Action.CREATE),
        ("terraform_data.third", Action.CREATE),
    )
    progress = follow(plan, lines("failed-part-way.jsonl"))
    assert progress.is_partial
    assert not progress.ok
    assert progress.done == 1
    assert [step.address for step in progress.failed] == ["terraform_data.second"]
    assert [step.address for step in progress.never_reached] == ["terraform_data.third"]


def test_a_resource_that_errored_counts_as_something_that_moved():
    """A create that errors may have made the object and marked it tainted, so
    the workspace matches neither the before nor the after. That is the state
    worth flagging, even when it is the only resource in the plan."""
    plan = a_plan(("terraform_data.second", Action.CREATE))
    progress = follow(plan, lines("failed-part-way.jsonl"))
    assert progress.failed
    assert progress.is_partial


def test_an_apply_that_never_started_anything_is_not_partial():
    """Nothing was attempted, so there is nothing half-done to reconcile."""
    plan = a_plan(("terraform_data.third", Action.CREATE))
    progress = follow(plan, lines("failed-part-way.jsonl"))
    assert progress.never_reached
    assert not progress.is_partial


def test_the_failure_is_named_rather_than_left_as_a_state():
    plan = a_plan(("terraform_data.second", Action.CREATE))
    progress = follow(plan, lines("failed-part-way.jsonl"))
    assert progress.failure
    assert "errored" in progress.failure.lower() or "provisioner" in progress.failure.lower()


# --- reading the stream at all ---------------------------------------------


def test_a_line_that_is_not_json_is_skipped_rather_than_fatal():
    """`tofu` writes plain text to the same stream when something goes wrong
    early, and losing the apply over one line would be worse."""
    said = ["Error: something happened before the JSON started", '{"type":"version"}', ""]
    assert [event["type"] for event in read_events(said)] == ["version"]


def test_an_event_about_a_resource_the_plan_does_not_have_is_ignored():
    plan = a_plan(("terraform_data.api", Action.UPDATE))
    progress = Progress(steps=steps_for(plan))
    from backsight.engine.plan.applying import apply_event

    apply_event(
        progress,
        json.loads('{"type":"apply_start","hook":{"resource":{"addr":"terraform_data.ghost"}}}'),
    )
    assert progress.steps[0].stage is Stage.WAITING


def test_the_plan_the_stream_belongs_to_can_be_read_from_the_same_capture():
    """The steps come from the plan document, so the two agree by construction."""
    document = json.loads(
        (FIXTURES.parent / "example" / "terraform.tfstate").read_text(encoding="utf-8")
    )
    assert document["version"]
    plan = parse({"format_version": "1.2", "terraform_version": "1.12.6", "resource_changes": []})
    assert steps_for(plan) == []
