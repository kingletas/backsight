"""Expansion, resolved values, and the one thing that must never come out."""

import json
from pathlib import Path

import pytest

from backsight.engine.insight.expressions import (
    SENSITIVE,
    UNKNOWN,
    Resolved,
    all_resolved,
    expansion,
    resolved,
)

ROOT = Path(__file__).resolve().parents[2]
PLAN = json.loads((ROOT / "fixtures" / "plan" / "expansion-and-sensitive.json").read_text())


# --- expansion ------------------------------------------------------------


def test_for_each_keys_are_known_before_anything_is_applied():
    """FR-DBG-03: the largest single source of HCL confusion, answered inline."""
    found = expansion(PLAN, "terraform_data.subnets")
    assert found.instances == 3
    assert found.keys == ("eu-west-1a", "eu-west-1b", "eu-west-1c")
    assert found.by_count is False
    assert found.summary() == ('3 instances · keys "eu-west-1a", "eu-west-1b", "eu-west-1c"')


def test_count_expands_to_a_number_rather_than_named_keys():
    found = expansion(PLAN, "terraform_data.counted")
    assert found.by_count is True
    assert found.summary() == "2 instances"


def test_asking_about_one_instance_answers_about_the_declaration():
    """`aws_subnet.this[0]` and `aws_subnet.this` are one declaration."""
    assert expansion(PLAN, 'terraform_data.subnets["eu-west-1a"]').instances == 3


def test_a_resource_with_no_expansion_has_no_instances():
    assert expansion(PLAN, "terraform_data.with_secret").instances == 0
    assert expansion(PLAN, "terraform_data.with_secret").summary() == "no instances"


# --- resolved values ------------------------------------------------------


def test_a_known_value_is_shown():
    found = resolved(PLAN, 'terraform_data.subnets["eu-west-1a"]', "input")
    assert found.is_showable
    assert found.display == '"eu-west-1a"'


def test_an_unknown_value_says_so_rather_than_showing_null():
    """A large class of "why is my plan doing that" is answered by seeing this."""
    found = resolved(PLAN, "terraform_data.with_secret", "output")
    assert found.known is False
    assert found.display == UNKNOWN


def test_an_attribute_the_plan_does_not_mention_is_none():
    assert resolved(PLAN, "terraform_data.with_secret", "invented") is None


def test_a_resource_that_is_not_in_the_plan_is_none():
    assert resolved(PLAN, "terraform_data.nowhere", "input") is None


# --- the one that must never come out -------------------------------------


def test_a_sensitive_value_is_never_shown():
    """FR-DBG-06. No setting turns this off, and there is no other accessor."""
    found = resolved(PLAN, "terraform_data.with_secret", "input")
    assert found.sensitive is True
    assert found.display == SENSITIVE
    assert found.is_showable is False


def test_the_secret_is_in_the_plan_file_which_is_why_this_matters():
    """The plan holds it in plain text; only `after_sensitive` says not to look."""
    change = next(
        c for c in PLAN["resource_changes"] if c["address"] == "terraform_data.with_secret"
    )
    assert change["change"]["after"]["input"] == "hunter2"
    assert change["change"]["after_sensitive"]["input"] is True


def test_no_public_accessor_returns_a_sensitive_value():
    """The value is private and `display` refuses. That is the whole guard."""
    found = resolved(PLAN, "terraform_data.with_secret", "input")
    public = [name for name in dir(found) if not name.startswith("_")]
    for name in public:
        rendered = str(getattr(found, name))
        assert "hunter2" not in rendered, f"{name} leaks the value"


def test_listing_every_attribute_still_hides_the_sensitive_one():
    found = all_resolved(PLAN, "terraform_data.with_secret")
    assert found
    assert all("hunter2" not in item.display for item in found)
    assert any(item.display == SENSITIVE for item in found)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("text", '"text"'), (3, "3"), (True, "True"), (None, "null")],
)
def test_values_are_rendered_the_way_a_person_reads_them(value, expected):
    assert Resolved(attribute="a", _value=value).display == expected
