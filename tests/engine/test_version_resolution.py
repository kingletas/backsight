"""The lock file decides which schema is served, never the newest available.

The fixtures are two real captures of `hashicorp/random`. `random_bytes` exists
in 3.6.3 and not in 3.5.1, so a workspace pinned at 3.5.1 being offered it is a
failure anyone can see.
"""

import json
from pathlib import Path

import pytest

from backsight.engine.schema.index import SchemaIndex, build
from backsight.engine.schema.resolution import parse_version, resolve, satisfies
from backsight.engine.workspace.discovery import discover

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "fixtures" / "schema"
RANDOM = "registry.opentofu.org/hashicorp/random"


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    """Both versions of the same provider, indexed side by side."""
    database = tmp_path_factory.mktemp("versions") / "schema.db"
    for version in ("3.5.1", "3.6.3"):
        schema = json.loads((SCHEMAS / f"random-{version}.json").read_text(encoding="utf-8"))
        build(schema, database, {RANDOM: version})
    with SchemaIndex(database) as opened:
        yield opened


def test_both_versions_are_indexed(index):
    assert index.providers() == [(RANDOM, "3.5.1"), (RANDOM, "3.6.3")]


def test_the_newer_version_has_a_resource_the_older_does_not(index):
    """If this ever stops being true the rest of this file proves nothing."""
    assert index.resource("random_bytes", provider_version="3.6.3") is not None
    assert index.resource("random_bytes", provider_version="3.5.1") is None


def test_a_workspace_pinned_to_the_older_version_is_served_the_older_one(tmp_path, index):
    """The whole point of the task."""
    (tmp_path / "main.tf").write_text(
        "terraform {\n"
        "  required_providers {\n"
        '    random = { source = "hashicorp/random", version = ">= 3.5" }\n'
        "  }\n"
        "}\n"
    )
    (tmp_path / ".terraform.lock.hcl").write_text(
        f'provider "{RANDOM}" {{\n  version     = "3.5.1"\n  constraints = ">= 3.5"\n}}\n'
    )
    module = discover(tmp_path).modules[0]
    provider = module.provider("random")
    chosen = resolve(
        "random",
        locked_version=provider.locked_version,
        constraint=provider.constraint,
        indexed=[version for address, version in index.providers() if address == RANDOM],
    )
    assert chosen.version == "3.5.1"
    assert chosen.pinned is True
    assert index.resource("random_bytes", provider_version=chosen.version) is None


def test_with_no_lock_file_the_newest_matching_version_is_served_and_said_to_be_unpinned():
    chosen = resolve("random", locked_version=None, constraint=">= 3.5", indexed=["3.5.1", "3.6.3"])
    assert chosen.version == "3.6.3"
    assert chosen.pinned is False
    assert "no lock file" in chosen.reason


def test_a_locked_version_that_is_not_indexed_serves_nothing(index):
    """Serving a different version because the right one is missing is the failure."""
    chosen = resolve(
        "random", locked_version="3.4.0", constraint=">= 3.0", indexed=["3.5.1", "3.6.3"]
    )
    assert chosen.servable is False
    assert chosen.version is None
    assert "not indexed" in chosen.reason


def test_a_constraint_nothing_satisfies_serves_nothing():
    chosen = resolve("random", locked_version=None, constraint=">= 9.0", indexed=["3.6.3"])
    assert chosen.servable is False
    assert ">= 9.0" in chosen.reason


def test_an_unreadable_constraint_serves_nothing_rather_than_guessing():
    assert satisfies("3.6.3", "whatever the platform team meant") is False


@pytest.mark.parametrize(
    ("version", "constraint", "expected"),
    [
        ("5.82.2", "~> 5.82", True),
        ("5.83.0", "~> 5.82", True),
        ("6.0.0", "~> 5.82", False),
        ("5.81.0", "~> 5.82", False),
        ("3.6.3", ">= 3.0, < 4.0", True),
        ("4.0.0", ">= 3.0, < 4.0", False),
        ("3.6.3", "3.6.3", True),
        ("3.6.3", "!= 3.6.3", False),
        ("3.6.3", None, True),
        ("3.6", ">= 3.6.0", True),
    ],
)
def test_constraints_are_read_the_way_terraform_reads_them(version, constraint, expected):
    assert satisfies(version, constraint) is expected


def test_versions_sort_by_number_and_not_as_text():
    """`3.10.0` is above `3.9.0`. Sorting these as strings puts it below."""
    assert parse_version("3.10.0") > parse_version("3.9.0")
    chosen = resolve("random", locked_version=None, constraint=None, indexed=["3.9.0", "3.10.0"])
    assert chosen.version == "3.10.0"
