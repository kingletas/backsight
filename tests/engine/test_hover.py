"""What holding the pointer over an attribute says.

The point of the file: whether an attribute forces replacement is answered from
the plan, and when there is no plan the answer is *not known*, never *no*.
"""

import gzip
import json
from pathlib import Path

import pytest

from backsight.engine.insight.hover import Replacement, hover_at, word_at
from backsight.engine.plan.model import parse
from backsight.engine.schema.index import SchemaIndex, build

ROOT = Path(__file__).resolve().parents[2]
VERSIONS = {
    "registry.opentofu.org/hashicorp/aws": "5.82.2",
    "registry.opentofu.org/hashicorp/local": "2.5.2",
    "registry.opentofu.org/hashicorp/null": "3.2.3",
    "registry.opentofu.org/hashicorp/random": "3.6.3",
}

SOURCE = b"""resource "aws_security_group" "db" {
  name        = "db"
  description = "database access"
  vpc_id      = "vpc-0123456789abcdef0"
}
"""


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    with gzip.open(ROOT / "fixtures" / "schema" / "providers-schema.json.gz", "rt") as handle:
        schema = json.load(handle)
    database = tmp_path_factory.mktemp("hover") / "schema.db"
    build(schema, database, VERSIONS)
    with SchemaIndex(database) as opened:
        yield opened


def offset_of(needle: bytes, source: bytes = SOURCE) -> int:
    """Points at the middle of a word, which is where a pointer usually lands."""
    return source.index(needle) + len(needle) // 2


def test_the_word_under_the_pointer_is_found_from_the_middle():
    word, start, end = word_at(SOURCE, offset_of(b"description"))
    assert word == "description"
    assert SOURCE[start:end] == b"description"


def test_hover_reports_the_type_and_whether_it_is_required(index):
    found = hover_at(SOURCE, offset_of(b"description"), index)
    assert found.name == "description"
    assert found.resource_type == "aws_security_group"
    assert found.type_label == "string"
    assert found.requirement == "optional"


def test_hover_over_something_that_is_not_an_attribute_says_nothing(index):
    assert hover_at(SOURCE, 2, index) is None


def test_hover_over_an_attribute_the_schema_does_not_have_says_nothing(index):
    source = b'resource "aws_security_group" "db" {\n  invented = "x"\n}\n'
    assert hover_at(source, offset_of(b"invented", source), index) is None


def test_with_no_plan_replacement_is_unknown_and_never_no(index):
    """The distinction the whole feature turns on."""
    found = hover_at(SOURCE, offset_of(b"vpc_id"), index)
    assert found.replacement is Replacement.UNKNOWN
    assert found.forces_replacement is False
    assert "Save the file" in found.replacement_detail


def test_hover_uses_the_plan_when_one_is_given(index):
    """A plan that names this attribute as the cause reads as forcing."""
    document = {
        "format_version": "1.2",
        "terraform_version": "1.12.6",
        "resource_changes": [
            {
                "address": "aws_security_group.db",
                "type": "aws_security_group",
                "name": "db",
                "mode": "managed",
                "provider_name": "registry.opentofu.org/hashicorp/aws",
                "action_reason": "replace_because_cannot_update",
                "change": {
                    "actions": ["delete", "create"],
                    "before": {"vpc_id": "vpc-old"},
                    "after": {"vpc_id": "vpc-new"},
                    "replace_paths": [["vpc_id"]],
                },
            }
        ],
    }
    plan = parse(document)
    forced = hover_at(SOURCE, offset_of(b"vpc_id"), index, plan=plan)
    assert forced.replacement is Replacement.FORCES
    assert forced.forces_replacement is True
    assert "is why" in forced.replacement_detail

    safe = hover_at(SOURCE, offset_of(b"description"), index, plan=plan)
    assert safe.replacement is Replacement.DOES_NOT
    assert safe.forces_replacement is False


def test_a_resource_the_plan_does_not_mention_is_unknown_rather_than_safe(index):
    """A plan covering other resources says nothing about this one."""
    document = {
        "format_version": "1.2",
        "terraform_version": "1.12.6",
        "resource_changes": [
            {
                "address": "aws_instance.other",
                "type": "aws_instance",
                "name": "other",
                "mode": "managed",
                "provider_name": "aws",
                "change": {"actions": ["create"], "before": None, "after": {}},
            }
        ],
    }
    found = hover_at(SOURCE, offset_of(b"vpc_id"), index, plan=parse(document))
    assert found.replacement is Replacement.UNKNOWN
    assert "not in the current plan" in found.replacement_detail


def test_hover_says_nothing_about_a_default_because_the_schema_has_none(index):
    """Decision 001. FR-SCH-05 asks for a default; the format has no such field."""
    found = hover_at(SOURCE, offset_of(b"description"), index)
    assert not hasattr(found, "default")


def test_a_sensitive_attribute_is_flagged(index):
    source = b'resource "aws_db_instance" "main" {\n  password = "x"\n}\n'
    found = hover_at(source, offset_of(b"password", source), index)
    assert found.sensitive is True


def test_a_read_only_attribute_says_so_rather_than_optional(index):
    source = b'resource "aws_security_group" "db" {\n  arn = "x"\n}\n'
    found = hover_at(source, offset_of(b"arn", source), index)
    assert found.requirement == "read-only"


def test_a_module_prefix_is_used_when_looking_the_resource_up(index):
    """A resource inside a module has a longer address in the plan than in the file."""
    document = {
        "format_version": "1.2",
        "terraform_version": "1.12.6",
        "resource_changes": [
            {
                "address": "module.network.aws_security_group.db",
                "type": "aws_security_group",
                "name": "db",
                "mode": "managed",
                "provider_name": "aws",
                "change": {"actions": ["delete", "create"], "replace_paths": [["vpc_id"]]},
            }
        ],
    }
    plan = parse(document)
    without = hover_at(SOURCE, offset_of(b"vpc_id"), index, plan=plan)
    assert without.replacement is Replacement.UNKNOWN
    with_prefix = hover_at(
        SOURCE, offset_of(b"vpc_id"), index, plan=plan, module_prefix="module.network"
    )
    assert with_prefix.replacement is Replacement.FORCES
