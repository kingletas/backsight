"""Reading the state back after an apply. "Applied" is not "working"."""

from __future__ import annotations

import json
from pathlib import Path

from backsight.engine.plan.model import Action, Plan, ResourceChange
from backsight.engine.plan.verifying import addresses_in, read_state, verify

FIXTURES = Path(__file__).resolve().parents[1].parent / "fixtures"


def a_plan(*pairs) -> Plan:
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
            for address, action in pairs
        ),
    )


def real_state() -> dict:
    return json.loads((FIXTURES / "apply" / "after-succeeded.tfstate").read_text(encoding="utf-8"))


def test_it_reads_the_addresses_out_of_a_real_state_file():
    found = addresses_in(real_state())
    assert "terraform_data.api" in found
    assert "terraform_data.worker" in found
    assert "terraform_data.old_cache" not in found


def test_an_apply_that_did_what_it_said_verifies():
    plan = a_plan(
        ("terraform_data.api", Action.UPDATE),
        ("terraform_data.database", Action.REPLACE),
        ("terraform_data.worker", Action.CREATE),
        ("terraform_data.old_cache", Action.DELETE),
    )
    found = verify(plan, FIXTURES, state=real_state())
    assert found.ok
    assert "as the plan intended" in found.summary


def test_a_resource_the_plan_created_that_is_not_there_is_named():
    plan = a_plan(("terraform_data.ghost", Action.CREATE))
    found = verify(plan, FIXTURES, state=real_state())
    assert not found.ok
    assert [check.address for check in found.disagreements] == ["terraform_data.ghost"]
    assert "did not end up as the plan said" in found.summary


def test_a_resource_the_plan_destroyed_that_is_still_there_is_named():
    plan = a_plan(("terraform_data.api", Action.DELETE))
    found = verify(plan, FIXTURES, state=real_state())
    assert not found.ok
    assert found.disagreements[0].expected == "gone"
    assert found.disagreements[0].found == "present"


def test_no_state_to_read_says_so_rather_than_passing():
    """A remote backend's state is not beside the configuration, and claiming
    everything is fine because there was nothing to check is the worst answer."""
    plan = a_plan(("terraform_data.api", Action.CREATE))
    found = verify(plan, Path("/nowhere-at-all"))
    assert not found.ok
    assert "could not be read back" in found.summary


def test_unreadable_state_is_the_same_answer(tmp_path):
    (tmp_path / "terraform.tfstate").write_text("{ not json", encoding="utf-8")
    assert read_state(tmp_path) is None
    assert not verify(a_plan(("a.b", Action.CREATE)), tmp_path).ok


def test_a_counted_resource_keeps_its_key_in_the_address():
    document = {
        "resources": [
            {
                "mode": "managed",
                "type": "terraform_data",
                "name": "shard",
                "instances": [{"index_key": 0}, {"index_key": 1}, {"index_key": "east"}],
            }
        ]
    }
    assert addresses_in(document) == {
        "terraform_data.shard[0]",
        "terraform_data.shard[1]",
        'terraform_data.shard["east"]',
    }


def test_a_data_source_is_not_something_the_plan_creates():
    document = {"resources": [{"mode": "data", "type": "terraform_data", "name": "read"}]}
    assert addresses_in(document) == set()
