"""The plan model, over every plan fixture.

Replacement is read from the plan, never inferred from a before/after
comparison. Getting that wrong means telling somebody the wrong resource is
about to be destroyed, which is the one mistake this product cannot make.
"""

from pathlib import Path

import pytest

from backsight.engine.plan.model import Action, parse, read

ROOT = Path(__file__).resolve().parents[2]
PLANS = ROOT / "fixtures" / "plan"
NAMES = ("create", "update", "replace", "destroy", "moved", "rename-unsafe")


@pytest.fixture(scope="module")
def plans():
    return {name: read(PLANS / f"{name}.json") for name in NAMES}


@pytest.mark.parametrize("name", NAMES)
def test_every_fixture_parses(name, plans):
    plan = plans[name]
    assert plan.format_version
    assert plan.engine_version
    assert plan.errored is False


def test_a_create_plan_reads_as_a_create(plans):
    plan = plans["create"]
    assert [c.action for c in plan.changes] == [Action.CREATE]
    assert plan.summary() == "1 to add"
    assert plan.is_destructive is False


def test_an_update_plan_reads_as_an_in_place_change(plans):
    plan = plans["update"]
    assert [c.action for c in plan.changes] == [Action.UPDATE]
    assert plan.is_destructive is False
    change = plan.change_at("terraform_data.api")
    assert change.attribute("input").before == "one"
    assert change.attribute("input").after == "two"


def test_a_replacement_reads_as_one_change_and_not_two(plans):
    """The JSON says `["delete", "create"]`. A person is doing one thing."""
    plan = plans["replace"]
    assert [c.action for c in plan.changes] == [Action.REPLACE]
    assert plan.summary() == "1 to replace"
    assert plan.is_destructive is True


def test_the_replacement_reason_is_read_and_not_inferred(plans):
    change = plans["replace"].change_at("terraform_data.api")
    assert change.action_reason == "replace_because_cannot_update"
    assert change.replace_paths == (("triggers_replace",),)
    assert change.replacing_attributes == ("triggers_replace",)


def test_the_attribute_that_forces_replacement_is_marked(plans):
    """Decision 001: this is the only truthful source in the product."""
    plan = plans["replace"]
    assert plan.forces_replacement("terraform_data.api", "triggers_replace") is True
    assert plan.forces_replacement("terraform_data.api", "input") is False
    change = plan.change_at("terraform_data.api")
    assert change.attribute("triggers_replace").forces_replacement is True
    assert change.attribute("input").forces_replacement is False


def test_an_attribute_that_changed_without_forcing_replacement_is_not_blamed(plans):
    """`input` changed too. Only one attribute caused the replacement."""
    change = plans["replace"].change_at("terraform_data.api")
    assert change.attribute("input").changed is True
    assert change.attribute("input").forces_replacement is False


def test_forcing_replacement_is_false_for_a_resource_not_in_the_plan(plans):
    assert plans["replace"].forces_replacement("aws_instance.nothing", "x") is False


def test_a_destroy_plan_reads_as_a_destroy(plans):
    plan = plans["destroy"]
    assert [c.action for c in plan.changes] == [Action.DELETE]
    assert plan.is_destructive is True
    assert plan.summary() == "1 to destroy"


def test_a_rename_with_a_moved_block_destroys_nothing(plans):
    """One half of the ground truth the refactoring milestone rests on."""
    plan = plans["moved"]
    assert [c.action for c in plan.changes] == [Action.NO_OP]
    assert plan.is_destructive is False
    assert plan.effective == ()
    assert plan.summary() == "no changes"


def test_the_same_rename_without_one_destroys_something(plans):
    """The other half, and the reason the verification gate exists."""
    plan = plans["rename-unsafe"]
    assert sorted(c.action.value for c in plan.changes) == ["create", "delete"]
    assert plan.is_destructive is True


def test_an_unknown_value_is_marked_rather_than_shown_as_none(plans):
    """`output` is computed. Showing it as null would be a lie about the plan."""
    change = plans["update"].change_at("terraform_data.api")
    assert change.attribute("output").unknown is True


def test_a_sensitive_value_is_marked(plans):
    change = plans["replace"].change_at("terraform_data.api")
    assert change.attribute("triggers_replace").sensitive is True


def test_a_module_address_is_split_from_the_resource():
    document = {
        "format_version": "1.0",
        "terraform_version": "1.12.6",
        "resource_changes": [
            {
                "address": "module.vpc.module.subnets.aws_subnet.this[0]",
                "type": "aws_subnet",
                "name": "this",
                "mode": "managed",
                "provider_name": "registry.opentofu.org/hashicorp/aws",
                "change": {"actions": ["create"], "before": None, "after": {}},
            }
        ],
    }
    change = parse(document).changes[0]
    assert change.module == "module.vpc.module.subnets"
    assert change.type == "aws_subnet"


def test_a_replacement_written_create_before_destroy_is_still_one_replacement():
    """`create_before_destroy` reverses the order. It is the same operation."""
    document = {
        "format_version": "1.0",
        "terraform_version": "1.12.6",
        "resource_changes": [
            {
                "address": "aws_instance.api",
                "type": "aws_instance",
                "name": "api",
                "mode": "managed",
                "provider_name": "aws",
                "change": {"actions": ["create", "delete"], "before": {}, "after": {}},
            }
        ],
    }
    assert parse(document).changes[0].action is Action.REPLACE


def test_an_action_list_nobody_has_seen_is_refused_rather_than_guessed():
    document = {
        "format_version": "1.0",
        "terraform_version": "1.12.6",
        "resource_changes": [
            {
                "address": "a.b",
                "type": "a",
                "name": "b",
                "mode": "managed",
                "provider_name": "p",
                "change": {"actions": ["update", "delete", "create"]},
            }
        ],
    }
    with pytest.raises(ValueError, match="unrecognised plan actions"):
        parse(document)


def test_counts_are_by_action():
    document = {
        "format_version": "1.0",
        "terraform_version": "1.12.6",
        "resource_changes": [
            {
                "address": f"null_resource.n{n}",
                "type": "null_resource",
                "name": f"n{n}",
                "mode": "managed",
                "provider_name": "null",
                "change": {"actions": actions},
            }
            for n, actions in enumerate(
                [["create"], ["create"], ["update"], ["delete", "create"], ["delete"]]
            )
        ],
    }
    plan = parse(document)
    assert plan.counts() == {
        Action.CREATE: 2,
        Action.UPDATE: 1,
        Action.REPLACE: 1,
        Action.DELETE: 1,
    }
    assert plan.summary() == "2 to add, 1 to change, 1 to replace, 1 to destroy"
