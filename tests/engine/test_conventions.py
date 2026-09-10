"""House rules filled into a snippet before anybody sees it."""

from __future__ import annotations

from backsight.engine.hcl.navigation import blocks
from backsight.engine.library.conventions import House, apply, from_settings
from backsight.engine.library.placeholders import resolve
from backsight.engine.settings.layers import Settings

BUCKET = 'resource "aws_s3_bucket" "${1:name}" {\n  bucket = "${2}"\n  tags = {\n    ${3}\n  }\n}\n'
NO_TAGS = 'resource "terraform_data" "${1:name}" {\n  input = "${2}"\n}\n'


def test_nothing_configured_changes_nothing():
    assert apply(BUCKET, House()) == BUCKET


def test_a_naming_pattern_reaches_the_first_placeholder():
    said = apply(BUCKET, House(naming="acme-{environment}-{name}"), environment="prod")
    assert '"${1:acme-prod-name}"' in said


def test_the_braces_are_ours_and_are_filled_in_here():
    """An HCL interpolation cannot go in a pattern: a placeholder default ends
    at its first `}` and would cut one in half."""
    assert House(naming="x-${var.environment}").usable_naming == ""
    assert apply(BUCKET, House(naming="x-${var.environment}")) == BUCKET


def test_an_unknown_environment_says_so_rather_than_leaving_a_brace():
    said = apply(BUCKET, House(naming="{environment}-{name}"))
    assert "{environment}" not in said
    assert "environment-name" in said


def test_tags_are_filled_where_a_snippet_has_them():
    said = apply(BUCKET, House(tags={"Owner": "platform", "ManagedBy": "terraform"}))
    assert 'Owner     = "platform"' in said
    assert 'ManagedBy = "terraform"' in said


def test_a_snippet_with_no_tags_block_does_not_grow_one():
    """Adding the argument to a resource type that has no such attribute
    produces a file that will not plan."""
    assert apply(NO_TAGS, House(tags={"Owner": "platform"})) == NO_TAGS


def test_the_last_placeholder_survives_so_you_can_still_add_one():
    said = apply(BUCKET, House(tags={"Owner": "platform"}))
    assert "${3}" in said


def test_what_comes_out_is_still_terraform_that_parses():
    said = apply(BUCKET, House(naming="acme-{name}", tags={"Owner": "platform"}))
    assert blocks(resolve(said).text.encode("utf-8"))


def test_the_two_conventions_are_read_out_of_settings():
    settings = Settings(
        layers={
            "user": {
                "conventions.naming": "acme-{environment}-{name}",
                "conventions.tags": "Owner=platform, ManagedBy=terraform",
            }
        }
    )
    house = from_settings(settings)
    assert house.naming == "acme-{environment}-{name}"
    assert house.tags == {"Owner": "platform", "ManagedBy": "terraform"}


def test_a_malformed_tag_pair_is_skipped_rather_than_breaking_the_rest():
    settings = Settings(layers={"user": {"conventions.tags": "Owner=platform, nonsense, =x, y="}})
    assert from_settings(settings).tags == {"Owner": "platform"}


def test_nothing_configured_reads_as_nothing():
    assert not from_settings(Settings()).any
