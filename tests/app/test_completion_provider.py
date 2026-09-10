"""The completion engine, reachable from a buffer.

It has decided what can be written at a position since it was built, under a
latency budget, with its own tests — and nothing in the editor ever called it.
These check the adapter, not the decision.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import gi
import pytest

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")

from gi.repository import Adw, GtkSource  # noqa: E402

from backsight.app.completion import CALLED, Completions, install  # noqa: E402
from backsight.engine.schema.completion import Kind  # noqa: E402
from backsight.engine.schema.index import SchemaIndex, build  # noqa: E402

Adw.init()

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "schema" / "providers-schema.json.gz"
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
    database = tmp_path_factory.mktemp("completion") / "schema.db"
    build(schema, database, VERSIONS)
    with SchemaIndex(database) as opened:
        yield opened


def a_buffer(text: str, caret: str = "|"):
    where = text.index(caret)
    buffer = GtkSource.Buffer()
    buffer.set_text(text.replace(caret, ""))
    buffer.place_cursor(buffer.get_iter_at_offset(where))
    return buffer


class Context:
    """Only what the adapter reads from a real completion context."""

    def __init__(self, buffer):
        self._buffer = buffer

    def get_buffer(self):
        return self._buffer


def test_it_offers_what_the_engine_says(index):
    provider = Completions(lambda: index)
    found = provider._candidates(Context(a_buffer("|")), index)
    assert "resource" in [candidate.label for candidate in found]


def test_a_resource_label_offers_resource_types(index):
    provider = Completions(lambda: index)
    found = provider._candidates(Context(a_buffer('resource "aws_db_|" "main" {\n}\n')), index)
    labels = [candidate.label for candidate in found]
    assert "aws_db_instance" in labels
    assert all(name.startswith("aws_db_") for name in labels)


def test_required_arguments_come_first(index):
    """Ordering is half of telling required from optional; the list is the other."""
    provider = Completions(lambda: index)
    found = provider._candidates(
        Context(a_buffer('resource "aws_security_group" "db" {\n  |\n}\n')), index
    )
    required = [candidate.required for candidate in found]
    assert required == sorted(required, reverse=True)


def test_it_is_silent_with_no_schema_index():
    """A popup that opens empty is worse than one that never opens."""
    provider = Completions(lambda: None)
    assert provider._index_for() is None


def test_half_written_hcl_never_costs_the_keystroke(index):
    """Typing produces unparseable files constantly, and the popup is the most
    that may ever be lost to one."""
    provider = Completions(lambda: index)
    provider._candidates(Context(a_buffer('resource "a" { { { |')), index)
    provider._candidates(Context(a_buffer('"""|')), index)
    provider._candidates(Context(a_buffer("|")), index)


def test_every_kind_the_engine_offers_has_a_word_a_reader_would_use():
    """`RESOURCE_TYPE` is "resource" to somebody writing one."""
    for kind in (Kind.TOP_LEVEL, Kind.RESOURCE_TYPE, Kind.DATA_TYPE, Kind.ARGUMENT):
        assert kind in CALLED, kind


def test_it_is_installed_on_a_real_view():
    view = GtkSource.View()
    provider = install(view, lambda: None)
    assert provider.do_get_title() == "Terraform"


def test_every_page_gets_one(tmp_path: Path):
    import shutil

    from backsight.app.editor import Page

    source = Path(__file__).resolve().parents[2] / "fixtures" / "plannable" / "main.tf"
    where = tmp_path / "main.tf"
    shutil.copy(source, where)
    page = Page(where)
    # GtkSource.Completion has no getter for its providers, so the page keeps
    # the one it installed — which is also what a test needs to reach it.
    assert page.completion.do_get_title() == "Terraform"
