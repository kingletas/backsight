"""Provider prose, read from the two layouts providers actually ship.

Both files are real, fetched from each provider's own repository at the tag
matching the schema fixture. A reader written against one layout silently finds
nothing for the other, which is why there are two.
"""

from __future__ import annotations

import urllib.error
from pathlib import Path

import pytest

from backsight.engine.schema.documentation import (
    Mirror,
    NotASource,
    parse,
    repository,
    short_name,
    urls_for,
)

FIXTURES = Path(__file__).resolve().parents[1].parent / "fixtures" / "docs"
LEGACY = (FIXTURES / "aws-s3_bucket.html.markdown").read_text(encoding="utf-8")
MODERN = (FIXTURES / "local-file.md").read_text(encoding="utf-8")


def a_page(text: str, resource: str, source: str):
    return parse(text, resource=resource, provider=source, version="1.0.0")


# --- where a page lives ----------------------------------------------------


def test_a_provider_source_becomes_its_repository():
    assert repository("hashicorp/aws") == "hashicorp/terraform-provider-aws"


def test_the_resource_prefix_is_the_provider_name():
    assert short_name("aws_s3_bucket", "hashicorp/aws") == "s3_bucket"
    assert short_name("local_file", "hashicorp/local") == "file"


def test_a_resource_that_does_not_carry_the_prefix_is_left_alone():
    assert short_name("random_pet", "hashicorp/aws") == "random_pet"


def test_both_layouts_are_tried():
    found = urls_for("aws_s3_bucket", source="hashicorp/aws", version="5.82.2")
    assert found[0].endswith("website/docs/r/s3_bucket.html.markdown")
    assert found[1].endswith("docs/resources/s3_bucket.md")
    assert "/v5.82.2/" in found[0]


def test_a_data_source_looks_somewhere_else():
    found = urls_for("aws_ami", source="hashicorp/aws", version="5.82.2", kind="data_source")
    assert "/docs/d/" in found[0]
    assert "/data-sources/" in found[1]


def test_a_version_that_already_says_v_is_not_given_a_second_one():
    assert "/vv" not in urls_for("aws_s3_bucket", source="hashicorp/aws", version="v5.82.2")[0]


def test_a_source_that_would_change_which_server_is_asked_is_refused():
    """It comes out of a lock file in somebody's repository and goes in a URL."""
    for said in ("../../evil", "a//b", "a/b/c", "", "a b/c"):
        with pytest.raises(NotASource):
            urls_for("x", source=said, version="1.0.0")


# --- reading one -----------------------------------------------------------


def test_the_legacy_layout_reads():
    page = a_page(LEGACY, "aws_s3_bucket", "hashicorp/aws")
    assert page.summary == "Provides a S3 bucket resource."
    assert page.has_prose
    assert "Example Usage" in page.sections()


def test_the_modern_layout_reads_too():
    page = a_page(MODERN, "local_file", "hashicorp/local")
    assert page.summary == "Generates a local file with the given content."
    assert page.has_prose


BOTH = ((LEGACY, "aws_s3_bucket", "hashicorp/aws"), (MODERN, "local_file", "hashicorp/local"))


def test_the_front_matter_never_reaches_the_prose():
    for text, resource, source in BOTH:
        page = a_page(text, resource, source)
        assert not page.text.startswith("---")
        assert "page_title:" not in page.text


def test_it_finds_the_provider_own_examples():
    """The part worth having: they are the provider's, and they are correct."""
    page = a_page(LEGACY, "aws_s3_bucket", "hashicorp/aws")
    assert page.examples
    assert any('resource "aws_s3_bucket"' in one.body for one in page.examples)


def test_an_example_is_named_by_the_heading_above_it():
    page = a_page(LEGACY, "aws_s3_bucket", "hashicorp/aws")
    assert any("Private Bucket" in one.title for one in page.examples)


def test_every_example_is_terraform_that_parses():
    from backsight.engine.hcl.navigation import blocks

    for text, resource, source in BOTH:
        for one in a_page(text, resource, source).examples:
            assert blocks(one.body.encode("utf-8")), one.title


def test_a_page_with_no_front_matter_still_reads():
    page = a_page("# Something\n\nText.\n", "x", "a/b")
    assert page.has_prose
    assert page.summary == ""


# --- the mirror ------------------------------------------------------------


def test_nothing_is_fetched_unless_it_is_allowed(tmp_path):
    """An editor that reaches out the first time somebody hovers is doing
    something they did not ask for."""
    asked = []
    mirror = Mirror(fetch=lambda url: asked.append(url) or LEGACY, home=tmp_path)
    assert mirror.get("aws_s3_bucket", source="hashicorp/aws", version="5.82.2") is None
    assert asked == []


def test_once_allowed_it_fetches_and_keeps_it(tmp_path):
    asked = []

    def fetch(url):
        asked.append(url)
        return LEGACY

    mirror = Mirror(fetch=fetch, home=tmp_path, allowed=True)
    page = mirror.get("aws_s3_bucket", source="hashicorp/aws", version="5.82.2")
    assert page is not None
    assert len(asked) == 1

    # A second mirror, so it comes off disk rather than out of memory.
    again = Mirror(fetch=fetch, home=tmp_path, allowed=True)
    came_back = again.get("aws_s3_bucket", source="hashicorp/aws", version="5.82.2")
    assert came_back.summary == page.summary
    assert len(asked) == 1


def test_what_is_kept_works_with_nothing_allowed(tmp_path):
    """The whole point of a mirror rather than a browser tab."""
    Mirror(fetch=lambda url: LEGACY, home=tmp_path, allowed=True).get(
        "aws_s3_bucket", source="hashicorp/aws", version="5.82.2"
    )
    offline = Mirror(fetch=lambda url: pytest.fail("asked"), home=tmp_path, allowed=False)
    assert offline.get("aws_s3_bucket", source="hashicorp/aws", version="5.82.2") is not None


def test_the_second_layout_is_tried_when_the_first_is_not_there(tmp_path):
    asked = []

    def fetch(url):
        asked.append(url)
        if "website/docs" in url:
            raise urllib.error.HTTPError(url, 404, "no", {}, None)
        return MODERN

    mirror = Mirror(fetch=fetch, home=tmp_path, allowed=True)
    page = mirror.get("local_file", source="hashicorp/local", version="2.5.2")
    assert page is not None
    assert len(asked) == 2


def test_a_resource_neither_layout_has_is_a_silence(tmp_path):
    def fetch(url):
        raise urllib.error.HTTPError(url, 404, "no", {}, None)

    assert (
        Mirror(fetch=fetch, home=tmp_path, allowed=True).get(
            "aws_not_real", source="hashicorp/aws", version="5.82.2"
        )
        is None
    )


def test_a_registry_that_cannot_be_reached_is_a_gap_not_a_failure(tmp_path):
    """Documentation that will not load must never fail the thing somebody was
    actually doing."""

    def fetch(url):
        raise urllib.error.URLError("no route")

    assert (
        Mirror(fetch=fetch, home=tmp_path, allowed=True).get(
            "aws_s3_bucket", source="hashicorp/aws", version="5.82.2"
        )
        is None
    )


def test_it_says_what_is_mirrored_and_how_much(tmp_path):
    mirror = Mirror(fetch=lambda url: LEGACY, home=tmp_path, allowed=True)
    mirror.get("aws_s3_bucket", source="hashicorp/aws", version="5.82.2")
    found = mirror.mirrored()
    assert found
    assert found[0][1] == 1


def test_a_version_is_mirrored_on_its_own(tmp_path):
    """Never the newest: an argument that arrived two releases later is a
    suggestion that will not apply."""
    mirror = Mirror(fetch=lambda url: LEGACY, home=tmp_path, allowed=True)
    mirror.get("aws_s3_bucket", source="hashicorp/aws", version="5.82.2")
    assert mirror.cached("aws_s3_bucket", source="hashicorp/aws", version="5.0.0") is None
