"""Every fixture exists, is not empty, and parses.

A fixture that quietly went missing takes a whole milestone's tests down with a
confusing error somewhere else. This says so here instead.
"""

import gzip
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"

PLANS = ("create", "update", "replace", "destroy", "moved", "rename-unsafe")


def test_the_provenance_note_exists():
    """A fixture with no recorded origin is indistinguishable from an invented one."""
    text = (FIXTURES / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "OpenTofu" in text and "2026-09-06" in text


def test_the_provider_schema_is_present_and_parses():
    path = FIXTURES / "schema" / "providers-schema.json.gz"
    assert path.stat().st_size > 0
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        schema = json.load(handle)
    assert schema["format_version"] == "1.0"
    providers = schema["provider_schemas"]
    aws = providers["registry.opentofu.org/hashicorp/aws"]
    assert len(aws["resource_schemas"]) > 1000


def test_the_schema_still_carries_no_force_replacement_field():
    """Finding 001. If this ever fails, the finding is out of date and good news."""
    with gzip.open(FIXTURES / "schema" / "providers-schema.json.gz", "rt", encoding="utf-8") as h:
        schema = json.load(h)
    keys = set()

    def walk(block):
        for attribute in (block.get("attributes") or {}).values():
            keys.update(attribute)
        for nested in (block.get("block_types") or {}).values():
            walk(nested.get("block", {}))

    for provider in schema["provider_schemas"].values():
        for resource in (provider.get("resource_schemas") or {}).values():
            walk(resource["block"])
    assert keys == {
        "computed",
        "deprecated",
        "description",
        "description_kind",
        "optional",
        "required",
        "sensitive",
        "type",
    }


@pytest.mark.parametrize("name", PLANS)
def test_each_plan_fixture_is_present_and_parses(name):
    plan = json.loads((FIXTURES / "plan" / f"{name}.json").read_text(encoding="utf-8"))
    assert plan["format_version"]


def test_the_replacement_plan_names_the_attribute_that_caused_it():
    plan = json.loads((FIXTURES / "plan" / "replace.json").read_text(encoding="utf-8"))
    change = plan["resource_changes"][0]["change"]
    assert change["actions"] == ["delete", "create"]
    assert change["replace_paths"] == [["triggers_replace"]]


def test_the_matched_rename_pair_is_the_ground_truth_for_refactoring():
    """One is what a rename must look like. The other is what it must never do."""
    safe = json.loads((FIXTURES / "plan" / "moved.json").read_text(encoding="utf-8"))
    unsafe = json.loads((FIXTURES / "plan" / "rename-unsafe.json").read_text(encoding="utf-8"))
    assert [c["change"]["actions"] for c in safe["resource_changes"]] == [["no-op"]]
    assert sorted(a for c in unsafe["resource_changes"] for a in c["change"]["actions"]) == [
        "create",
        "delete",
    ]


def test_the_round_trip_corpus_is_present():
    corpus = sorted((FIXTURES / "hcl" / "ugly").glob("*.tf"))
    assert len(corpus) >= 20
    # One file is deliberately empty; the rest must have content.
    assert sum(1 for p in corpus if p.stat().st_size == 0) == 1


def test_the_workspace_fixture_has_the_shapes_the_discovery_test_needs():
    workspace = FIXTURES / "workspace"
    assert (workspace / "environments" / "prod" / ".terraform.lock.hcl").is_file()
    assert (workspace / "modules" / "vpc" / "main.tf").is_file()
    assert (workspace / "docs" / "notes.md").is_file()
    assert 'backend "s3"' in (workspace / "environments" / "prod" / "main.tf").read_text()
