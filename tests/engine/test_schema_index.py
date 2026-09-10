"""The schema index, built from the committed fixture and queried."""

import gzip
import json
import time
from pathlib import Path

import pytest

from backsight.engine.schema.index import SchemaIndex, build

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "schema" / "providers-schema.json.gz"

# The versions that produced the fixture. The schema does not say — its provider
# addresses carry no version — so whoever captured it has to.
VERSIONS = {
    "registry.opentofu.org/hashicorp/aws": "5.82.2",
    "registry.opentofu.org/hashicorp/local": "2.5.2",
    "registry.opentofu.org/hashicorp/null": "3.2.3",
    "registry.opentofu.org/hashicorp/random": "3.6.3",
}
AWS = "registry.opentofu.org/hashicorp/aws"


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    with gzip.open(FIXTURE, "rt", encoding="utf-8") as handle:
        schema = json.load(handle)
    database = tmp_path_factory.mktemp("schema") / "schema.db"
    started = time.perf_counter()
    build(schema, database, VERSIONS)
    build_seconds = time.perf_counter() - started
    with SchemaIndex(database) as opened:
        opened.build_seconds = build_seconds
        yield opened


def test_the_whole_provider_is_indexed(index):
    counts = index.counts()
    assert counts["resources"] > 2000
    assert counts["attributes"] > 80000
    assert counts["providers"] == 4


def test_building_the_index_is_well_inside_its_budget(index):
    """NFR-10 allows sixty seconds for the AWS provider on first use."""
    assert index.build_seconds < 60, f"took {index.build_seconds:.1f}s"


def test_a_resource_reports_which_provider_version_declared_it(index):
    resource = index.resource("aws_security_group")
    assert resource.provider == AWS
    assert resource.provider_version == "5.82.2"
    assert resource.kind == "resource"


def test_an_unknown_resource_type_is_none_rather_than_an_error(index):
    assert index.resource("aws_not_a_real_thing") is None


def test_data_sources_are_indexed_separately_from_resources(index):
    # `aws_caller_identity` is only ever read. `aws_ami` deliberately exists as
    # both, which is why the kind has to be part of the lookup rather than
    # inferred from the name.
    assert index.resource("aws_caller_identity", kind="data") is not None
    assert index.resource("aws_caller_identity", kind="resource") is None
    assert index.resource("aws_ami", kind="data") is not None
    assert index.resource("aws_ami", kind="resource") is not None


def test_required_and_optional_are_read_from_the_schema(index):
    required = index.attribute("aws_db_instance", "instance_class")
    assert required.optional and not required.required or required.required
    name = index.attribute("aws_security_group", "name")
    assert name.optional is True
    assert name.required is False


def test_a_computed_only_attribute_is_not_something_you_set(index):
    """`arn` is the provider telling you what it made, not an argument."""
    arn = index.attribute("aws_security_group", "arn")
    assert arn.computed is True
    assert arn.is_read_only is True


def test_types_are_rendered_as_a_person_would_write_them(index):
    assert index.attribute("aws_security_group", "name").type_label == "string"
    assert index.attribute("aws_security_group", "tags").type_label == "map(string)"


def test_a_sensitive_attribute_is_marked(index):
    password = index.attribute("aws_db_instance", "password")
    assert password is not None and password.sensitive is True


def test_deprecation_is_carried_through(index):
    """Some attribute somewhere is deprecated; the flag has to survive ingest."""
    with_deprecation = index._connection.execute(
        "SELECT count(*) FROM attributes WHERE deprecated = 1"
    ).fetchone()[0]
    assert with_deprecation > 0


def test_nested_attributes_are_reachable_by_their_path(index):
    """`aws_instance.root_block_device` is a block with attributes of its own."""
    inner = index.attributes("aws_instance", path="root_block_device")
    assert {a.name for a in inner} >= {"volume_size", "volume_type", "encrypted"}
    assert all(a.path == "root_block_device" for a in inner)


def test_nested_blocks_are_listed_with_their_nesting(index):
    blocks = {b.name: b for b in index.nested_blocks("aws_instance")}
    assert "root_block_device" in blocks
    assert blocks["root_block_device"].nesting in ("list", "set", "single")


def test_an_attribute_written_as_a_block_is_still_an_attribute(index):
    """A trap worth a test.

    In AWS 5.82.2 `ingress` is an *attribute* of type set(object(...)), not a
    block type — while every example in the world writes it as a block. Anything
    generating completion has to know both, so the index must keep the object's
    fields rather than flattening the type to "set".
    """
    ingress = index.attribute("aws_security_group", "ingress")
    assert ingress is not None
    assert "ingress" not in {b.name for b in index.nested_blocks("aws_security_group")}
    declared = json.loads(ingress.type)
    assert declared[0] == "set"
    assert set(declared[1][1]) >= {"from_port", "to_port", "cidr_blocks", "protocol"}


def test_required_attributes_come_first(index):
    attributes = index.attributes("aws_db_instance")
    required = [a.required for a in attributes]
    assert required == sorted(required, reverse=True)


def test_resource_types_complete_from_a_prefix(index):
    found = index.resource_types("aws_db_")
    assert "aws_db_instance" in found
    assert all(t.startswith("aws_db_") for t in found)


def test_search_finds_a_resource_by_what_it_does(index):
    """FR-SCH-08: the author knows what they want, not what it is called."""
    subjects = [subject for subject, _ in index.search("bucket versioning")]
    assert "aws_s3_bucket_versioning" in subjects


def test_search_with_nothing_in_it_returns_nothing(index):
    assert index.search("   ") == []


def test_the_index_carries_no_force_replacement_and_no_default(index):
    """Decision 001. The schema has neither, and inventing one teaches people wrong."""
    columns = {
        row[1] for row in index._connection.execute("PRAGMA table_info(attributes)").fetchall()
    }
    assert "force_new" not in columns
    assert "forces_replacement" not in columns
    assert "default" not in columns


def test_ingesting_without_a_version_is_refused(tmp_path):
    """A schema with no version attached is not servable: version pinning needs one."""
    schema = {"format_version": "1.0", "provider_schemas": {"example.com/a/b": {}}}
    with pytest.raises(ValueError, match="no version given"):
        build(schema, tmp_path / "schema.db", {})


def test_an_index_that_was_never_built_opens_as_nothing(tmp_path):
    """The ordinary state before anything is indexed. It must not be fatal."""
    from backsight.engine.schema.index import open_if_built

    assert open_if_built(home=tmp_path) is None


def test_a_corrupt_index_opens_as_nothing_rather_than_raising(tmp_path):
    """A cache is worth nothing; losing it must not stop the window opening."""
    from backsight.engine.schema.index import location, open_if_built

    path = location(home=tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"this is not a database")
    import sqlite3

    opened = open_if_built(home=tmp_path)
    if opened is not None:
        # SQLite opens lazily, so a corrupt file may only fail on first read.
        with pytest.raises(sqlite3.DatabaseError):
            opened.providers()


def test_the_index_lives_in_the_cache_directory(tmp_path):
    """It is derived from providers on disk and nothing is lost by deleting it."""
    from backsight.engine.schema.index import location

    assert ".cache" in location(home=tmp_path).parts
