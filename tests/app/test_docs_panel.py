"""Provider documentation beside the file, with its examples insertable."""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.docs_panel import NOTHING_YET, DocsPanel  # noqa: E402
from backsight.engine.schema.documentation import parse  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "docs"
LEGACY = (FIXTURES / "aws-s3_bucket.html.markdown").read_text(encoding="utf-8")


def a_page():
    return parse(LEGACY, resource="aws_s3_bucket", provider="hashicorp/aws", version="5.82.2")


def test_before_anything_it_says_what_to_do():
    assert DocsPanel().summary == NOTHING_YET


def test_searching_lists_what_the_index_found():
    found = [("aws_s3_bucket", "resource"), ("aws_ami", "data_source")]
    panel = DocsPanel(on_search=lambda term: found)
    panel.look_for("bucket")
    assert panel.matches() == ["aws_s3_bucket", "aws_ami"]


def test_an_empty_term_lists_nothing():
    panel = DocsPanel(on_search=lambda term: [("x", "resource")])
    panel.look_for("")
    assert panel.matches() == []


def test_choosing_one_asks_for_its_page():
    asked = []
    panel = DocsPanel(on_search=lambda term: [("aws_s3_bucket", "resource")], on_open=asked.append)
    panel.look_for("bucket")
    panel._open("aws_s3_bucket")
    assert asked == ["aws_s3_bucket"]


def test_a_page_shows_what_it_is_and_which_version(self=None):
    panel = DocsPanel()
    panel.show(a_page())
    assert panel.title == "aws_s3_bucket"
    assert panel.summary == "Provides a S3 bucket resource."
    assert "5.82.2" in panel._where.get_text()


def test_the_examples_are_the_provider_own_and_go_in_the_buffer():
    """Copying out of a browser is how an example arrives with the wrong
    indentation and a stray prompt character."""
    put = []
    panel = DocsPanel(on_insert=put.append)
    panel.show(a_page())
    assert panel.examples()
    assert all(name.startswith("Insert: ") for name in panel.examples())
    panel._examples.get_first_child().emit("clicked")
    assert put and 'resource "aws_s3_bucket"' in put[0]


def test_a_page_that_is_not_mirrored_says_so_rather_than_looking_broken():
    panel = DocsPanel()
    panel.waiting("Not mirrored yet.")
    assert panel.summary == "Not mirrored yet."
    assert panel.examples() == []


def test_showing_a_second_page_replaces_the_first():
    panel = DocsPanel()
    panel.show(a_page())
    first = len(panel.examples())
    panel.show(a_page())
    assert len(panel.examples()) == first


def test_a_search_that_raises_never_takes_the_panel_down():
    def explode(term):
        raise RuntimeError("the index is closed")

    panel = DocsPanel(on_search=explode)
    with pytest.raises(RuntimeError):
        panel.look_for("bucket")
