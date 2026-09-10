"""Resolved values and expansion, on the line that declares them."""

import json
from pathlib import Path

from backsight.engine.insight.expressions import SENSITIVE
from backsight.engine.insight.hints import for_attribute, for_plan, in_file
from backsight.engine.insight.source_map import SourceMap
from backsight.engine.workspace.discovery import discover

SOURCE = """locals {
  azs = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
}

variable "secret" {
  type      = string
  sensitive = true
  default   = "hunter2"
}

resource "terraform_data" "subnets" {
  for_each = toset(local.azs)
  input    = each.value
}

resource "terraform_data" "counted" {
  count = 2
  input = "n-${count.index}"
}

resource "terraform_data" "with_secret" {
  input = var.secret
}
"""

ROOT = Path(__file__).resolve().parents[2]
PLAN = json.loads((ROOT / "fixtures" / "plan" / "expansion-and-sensitive.json").read_text())


def mapped(tmp_path):
    (tmp_path / "main.tf").write_text(SOURCE)
    workspace = discover(tmp_path)
    return SourceMap.build(workspace, workspace.root_modules[0])


def test_a_for_each_hint_lands_on_the_line_that_expands(tmp_path):
    """FR-DBG-03: the key set is computable before anything is planned."""
    hints = for_plan(PLAN, mapped(tmp_path))
    subnets = next(h for h in hints if "keys" in h.text)
    assert subnets.line == 12
    assert subnets.text == '3 instances · keys "eu-west-1a", "eu-west-1b", "eu-west-1c"'


def test_a_count_hint_says_how_many_rather_than_naming_keys(tmp_path):
    hints = for_plan(PLAN, mapped(tmp_path))
    counted = next(h for h in hints if h.text == "2 instances")
    assert counted.line == 17


def test_a_resource_that_does_not_expand_gets_no_hint(tmp_path):
    """Hinting every attribute buries the two that matter."""
    hints = for_plan(PLAN, mapped(tmp_path))
    assert len(hints) == 2


def test_hints_come_back_in_line_order(tmp_path):
    lines = [h.line for h in for_plan(PLAN, mapped(tmp_path))]
    assert lines == sorted(lines)


def test_only_the_open_file_is_asked_for(tmp_path):
    hints = for_plan(PLAN, mapped(tmp_path))
    assert in_file(hints, tmp_path / "main.tf") == hints
    assert in_file(hints, tmp_path / "other.tf") == []


def test_hovering_an_attribute_says_what_it_resolved_to(tmp_path):
    hint = for_attribute(PLAN, mapped(tmp_path), 'terraform_data.subnets["eu-west-1a"]', "input")
    assert hint is not None
    assert hint.text == 'input → "eu-west-1a"'


def test_hovering_a_sensitive_attribute_shows_nothing_of_it(tmp_path):
    """The refusal is in the type; this only has to not go around it."""
    hint = for_attribute(PLAN, mapped(tmp_path), "terraform_data.with_secret", "input")
    assert hint is not None
    assert hint.text == f"input → {SENSITIVE}"
    assert "hunter2" not in hint.text


def test_an_attribute_that_is_not_in_the_plan_gives_no_hint(tmp_path):
    assert for_attribute(PLAN, mapped(tmp_path), "terraform_data.nowhere", "input") is None
