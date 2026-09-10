"""The parts of a stored body you fill in, against real Terraform.

The whole design turns on one thing: a digit right after `${` means a
placeholder, and HCL's own interpolation can never begin with one.
"""

from __future__ import annotations

from backsight.engine.library.placeholders import (
    has_placeholders,
    numbers_in,
    resolve,
    strip,
)


def test_a_body_with_nothing_to_fill_in_comes_back_unchanged():
    body = 'resource "aws_s3_bucket" "logs" {\n  bucket = "acme-logs"\n}\n'
    found = resolve(body)
    assert found.text == body
    assert found.stops == ()
    assert not found.has_stops


def test_hcl_interpolation_is_not_a_placeholder():
    """The reason the toolkit's own snippet engine cannot be used: it eats the
    brace. An HCL identifier cannot begin with a digit, so ours does not."""
    body = 'bucket = "${var.environment}-logs"\n'
    assert not has_placeholders(body)
    assert resolve(body).text == body
    assert strip(body) == body


def test_the_two_together_survive_intact():
    body = 'bucket = "${1:acme}-${var.environment}"\n'
    found = resolve(body)
    assert found.text == 'bucket = "acme-${var.environment}"\n'
    assert [stop.number for stop in found.stops] == [1]


def test_count_index_and_resource_references_are_left_alone():
    body = 'name = "web-${count.index}"\nid = "${aws_s3_bucket.this.id}"\n'
    assert resolve(body).text == body


def test_a_placeholder_records_where_its_default_landed():
    found = resolve('bucket = "${1:acme}"\n')
    stop = found.stops[0]
    assert found.text[stop.start : stop.end] == "acme"
    assert stop.default == "acme"
    assert stop.length == 4


def test_an_empty_placeholder_is_a_position_with_nothing_in_it():
    found = resolve('bucket = "${1}"\n')
    stop = found.stops[0]
    assert stop.start == stop.end
    assert found.text == 'bucket = ""\n'


def test_stops_are_ordered_by_number_not_by_position():
    """Tabbing follows the order whoever wrote the entry intended."""
    found = resolve("${2:second} ${1:first} ${3:third}")
    assert [stop.number for stop in found.stops] == [1, 2, 3]
    assert found.text == "second first third"


def test_the_end_marker_comes_after_everything():
    found = resolve('resource "${1:type}" "${2:name}" {\n  ${0}\n}\n')
    assert [stop.number for stop in found.stops] == [1, 2, 0]
    assert found.stops[-1].is_the_end
    assert found.has_stops


def test_a_body_that_is_only_an_end_marker_has_nothing_to_fill_in():
    found = resolve("terraform {\n  ${0}\n}\n")
    assert not found.has_stops
    assert found.stops[0].is_the_end


def test_the_same_number_twice_keeps_both_in_reading_order():
    found = resolve("${1:a} middle ${1:a}")
    assert len(found.stops) == 2
    assert found.stops[0].start < found.stops[1].start


def test_offsets_survive_a_default_longer_than_its_placeholder():
    found = resolve("x${1:aaaaaaaaaa}y${2:b}z")
    assert found.text == "xaaaaaaaaaaybz"
    for stop in found.stops:
        assert found.text[stop.start : stop.end] == stop.default


def test_numbers_are_read_in_the_order_they_appear():
    assert numbers_in("${2:b} ${1:a} ${0}") == [2, 1, 0]


def test_a_default_cannot_swallow_a_following_interpolation():
    """A default containing `${}` would be a body, not a default."""
    body = "${1:acme}-${var.thing}"
    found = resolve(body)
    assert found.stops[0].default == "acme"
    assert found.text == "acme-${var.thing}"
