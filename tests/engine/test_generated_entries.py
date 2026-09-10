"""Entries built from the real provider schema, so the library is never empty.

Against the committed AWS schema — nobody writes a snippet for a resource
before they need it, and by then they are already typing the thing it would
have saved.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from backsight.engine.library.entry import Source
from backsight.engine.library.generated import for_resource, matching
from backsight.engine.library.placeholders import resolve
from backsight.engine.schema.index import SchemaIndex, build

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "schema" / "providers-schema.json.gz"
VERSIONS = {
    "registry.opentofu.org/hashicorp/aws": "5.82.2",
    "registry.opentofu.org/hashicorp/local": "2.5.2",
    "registry.opentofu.org/hashicorp/null": "3.2.3",
    "registry.opentofu.org/hashicorp/random": "3.6.3",
}


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    with gzip.open(FIXTURE, "rt", encoding="utf-8") as handle:
        schema = json.load(handle)
    database = tmp_path_factory.mktemp("schema") / "schema.db"
    build(schema, database, VERSIONS)
    with SchemaIndex(database) as opened:
        yield opened


def test_a_real_resource_gets_a_short_and_a_full_entry(index):
    found = for_resource(index, "aws_s3_bucket")
    assert len(found) == 2
    assert "required only" in found[0].name
    assert "every argument" in found[1].name


def test_the_short_one_carries_only_what_cannot_be_left_out(index):
    short = for_resource(index, "aws_db_instance")[0]
    required = [a.name for a in index.attributes("aws_db_instance") if a.required]
    for name in required:
        assert name in short.body
    assert short.body.count("=") == len(required) + (0 if required else 0) or not required


def test_what_it_generates_is_valid_hcl(index):
    from backsight.engine.hcl.navigation import blocks

    for entry in for_resource(index, "aws_instance"):
        text = resolve(entry.body).text
        assert blocks(text.encode("utf-8")), entry.name


def test_the_name_is_the_first_thing_you_fill_in(index):
    entry = for_resource(index, "aws_s3_bucket")[0]
    assert '"${1:name}"' in entry.body
    assert resolve(entry.body).stops[0].default == "name"


def test_a_placeholder_is_shaped_like_the_type_it_stands_for(index):
    """A type arrives as `["list", "string"]` — JSON, not a word — and reading
    it as a word gave every argument a string placeholder, numbers included."""
    full = for_resource(index, "aws_s3_bucket")[1]
    assert "${6:false}" in full.body
    assert "= false" in resolve(full.body).text
    assert "# bool, optional" in full.body


def test_a_note_on_a_multi_line_value_goes_on_the_opening_line(index):
    """Trailing a closing brace, it reads as a comment about the brace."""
    full = for_resource(index, "aws_s3_bucket")[1]
    assert "= {  # map, optional" in full.body
    assert "}  # map" not in full.body


def test_the_full_one_says_which_arguments_are_optional(index):
    full = for_resource(index, "aws_s3_bucket")[1]
    assert ", optional" in full.body


def test_an_output_only_attribute_is_never_written_into_a_snippet(index):
    """It is something the resource tells you, not something you set, and a
    file that sets one will not apply."""
    for entry in for_resource(index, "aws_s3_bucket"):
        assert "\n  arn" not in entry.body
        assert "bucket_domain_name" not in entry.body


def test_terraform_own_reserved_names_are_never_written_either(index):
    """AWS declares `id` as optional-and-computed on nearly every resource and
    nobody can set it."""
    for type_ in ("aws_s3_bucket", "aws_instance", "aws_db_instance"):
        for entry in for_resource(index, type_):
            assert "\n  id " not in entry.body
            assert "\n  count " not in entry.body


def test_a_resource_the_schema_never_heard_of_gets_nothing(index):
    """An entry invented for an unknown resource is a confident guess about
    somebody else's provider."""
    assert for_resource(index, "aws_not_a_real_thing") == []


def test_a_resource_with_too_many_arguments_gets_only_the_short_one(index):
    """Past a point the full entry is a wall rather than a starting point.
    `aws_db_instance` has 78 arguments."""
    assert len(for_resource(index, "aws_db_instance")) == 1


def test_they_are_marked_as_generated_rather_than_as_somebody_work(index):
    for entry in for_resource(index, "aws_s3_bucket"):
        assert entry.source is Source.BUILT_IN
        assert not entry.source.is_editable
        assert entry.resource == "aws_s3_bucket"


def test_asking_by_prefix_answers_from_the_real_index(index):
    found = matching(index, "aws_s3_bucket", limit=3)
    assert found
    assert all("aws_s3_bucket" in entry.resource for entry in found)


def test_a_data_source_says_data_rather_than_resource(index):
    found = for_resource(index, "aws_ami", kind="data_source")
    if found:
        assert found[0].body.startswith('data "aws_ami"')
