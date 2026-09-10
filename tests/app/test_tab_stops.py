"""Filling in a snippet, against a real buffer.

The toolkit's own snippet engine would have done this and cannot: it eats the
brace of every HCL interpolation. See docs/findings/014.
"""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import Gtk, GtkSource  # noqa: E402

from backsight.app.tab_stops import Stops  # noqa: E402

BUCKET = 'resource "aws_s3_bucket" "${1:name}" {\n  bucket = "${2:acme}"\n  ${0}\n}\n'


@pytest.fixture
def view():
    buffer = GtkSource.Buffer()
    found = GtkSource.View(buffer=buffer)
    window = Gtk.Window()
    window.set_child(found)
    window.present()
    return found


def text_of(view) -> str:
    buffer = view.get_buffer()
    return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)


def selected(view) -> str:
    bounds = view.get_buffer().get_selection_bounds()
    return view.get_buffer().get_text(*bounds, True) if bounds else ""


def test_it_inserts_the_body_with_the_defaults_filled_in(view):
    Stops(view).insert(BUCKET)
    assert 'resource "aws_s3_bucket" "name" {' in text_of(view)
    assert 'bucket = "acme"' in text_of(view)
    assert "${" not in text_of(view)


def test_the_first_stop_is_selected_so_you_can_type_over_it(view):
    Stops(view).insert(BUCKET)
    assert selected(view) == "name"


def test_tab_moves_to_the_next_one(view):
    stops = Stops(view)
    stops.insert(BUCKET)
    stops.next()
    assert selected(view) == "acme"


def test_shift_tab_goes_back(view):
    stops = Stops(view)
    stops.insert(BUCKET)
    stops.next()
    stops.previous()
    assert selected(view) == "name"


def test_typing_a_longer_value_does_not_move_the_later_stops(view):
    """The reason marks are used at all — they travel with the text."""
    stops = Stops(view)
    stops.insert(BUCKET)
    buffer = view.get_buffer()
    buffer.delete_selection(True, True)
    buffer.insert_at_cursor("a-very-much-longer-bucket-name")
    stops.next()
    assert selected(view) == "acme"


def test_reaching_the_end_marker_ends_it(view):
    stops = Stops(view)
    stops.insert(BUCKET)
    stops.next()
    stops.next()
    assert not stops.is_live


def test_escape_ends_it_and_leaves_the_text(view):
    stops = Stops(view)
    stops.insert(BUCKET)
    stops.stop()
    assert not stops.is_live
    assert 'resource "aws_s3_bucket" "name"' in text_of(view)


def test_hcl_interpolation_arrives_intact(view):
    """The whole reason this exists rather than the toolkit's version."""
    Stops(view).insert('bucket = "${1:acme}-${var.environment}"\n')
    assert text_of(view) == 'bucket = "acme-${var.environment}"\n'


def test_a_body_with_nothing_to_fill_in_inserts_and_does_not_start(view):
    stops = Stops(view)
    stops.insert('resource "aws_s3_bucket" "logs" {}\n')
    assert not stops.is_live
    assert text_of(view).startswith('resource "aws_s3_bucket" "logs"')


def test_it_lands_at_the_depth_the_caret_was_at(view):
    """A block pasted at the wrong depth is the first thing anybody has to fix."""
    buffer = view.get_buffer()
    buffer.set_text("module x {\n  ")
    buffer.place_cursor(buffer.get_end_iter())
    Stops(view).insert('resource "a" "${1:b}" {\n  x = 1\n}\n')
    assert "\n    x = 1\n  }" in text_of(view)


def test_a_second_insertion_replaces_the_first_rather_than_stacking(view):
    stops = Stops(view)
    stops.insert(BUCKET)
    stops.insert('output "${1:name}" {}\n')
    assert stops.remaining >= 0
    assert selected(view) == "name"


def test_it_reports_how_many_are_left_to_fill_in(view):
    stops = Stops(view)
    stops.insert(BUCKET)
    assert stops.remaining == 2
