"""The example workspace shows what the product is for.

Two adds and nothing else is an empty diff wearing a demo's clothes. The first
plan a new person ever runs here has to contain the thing they are afraid of.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backsight.app.window import EXAMPLE_WORKSPACE

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "fixtures" / "example"


def test_the_app_points_at_it():
    assert EXAMPLE_WORKSPACE == EXAMPLE


def test_it_ships_with_state_so_the_first_plan_is_not_all_adds():
    stored = json.loads((EXAMPLE / "terraform.tfstate").read_text(encoding="utf-8"))
    assert len(stored["resources"]) == 3


def test_it_needs_no_provider_no_credentials_and_no_network():
    """A demo that cannot run on a plane is not the shortest path to anything."""
    source = (EXAMPLE / "main.tf").read_text(encoding="utf-8")
    assert 'resource "terraform_data"' in source
    assert "aws_" not in source and "provider " not in source


def test_something_in_state_is_absent_from_the_configuration():
    """Which is what makes the plan contain a destroy."""
    stored = json.loads((EXAMPLE / "terraform.tfstate").read_text(encoding="utf-8"))
    source = (EXAMPLE / "main.tf").read_text(encoding="utf-8")
    in_state = {entry["name"] for entry in stored["resources"]}
    assert [name for name in in_state if f'"{name}"' not in source]


def test_something_carries_a_trigger_that_no_longer_matches_state():
    """Which is what makes the plan contain a replace."""
    stored = json.loads((EXAMPLE / "terraform.tfstate").read_text(encoding="utf-8"))
    source = (EXAMPLE / "main.tf").read_text(encoding="utf-8")
    triggers = set()
    for entry in stored["resources"]:
        for instance in entry.get("instances") or []:
            # The engine stores it as a typed value rather than a bare string.
            found = (instance.get("attributes") or {}).get("triggers_replace")
            if isinstance(found, dict) and isinstance(found.get("value"), str):
                triggers.add(found["value"])
    assert triggers, "nothing in state carries a trigger, so nothing can replace"
    assert not [value for value in triggers if f'"{value}"' in source]


@pytest.mark.sandbox
def test_the_plan_really_does_contain_all_four():
    import shutil
    import tempfile

    from backsight.engine.plan.execution import speculative

    with tempfile.TemporaryDirectory() as scratch:
        where = Path(scratch) / "example"
        shutil.copytree(EXAMPLE, where)
        outcome = speculative(where)
        assert outcome.plan is not None, outcome.output
        actions = [
            row.tone
            for row in __import__("backsight.engine.plan.view", fromlist=["rows"]).rows(
                outcome.plan
            )
        ]
        assert "add" in actions
        assert "change" in actions
        assert "destroy" in actions or "replace" in actions
