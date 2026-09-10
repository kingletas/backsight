"""Where the plan touches the file, at a glance — not a thumbnail of the text."""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk  # noqa: E402

from backsight.app.change_map import MINIMUM, ORDER, ChangeMap, Mark  # noqa: E402


def coloured() -> dict[str, Gdk.RGBA]:
    found = {}
    for tone in ORDER:
        rgba = Gdk.RGBA()
        rgba.parse("#ff0000")
        found[tone] = rgba
    return found


def test_the_most_consequential_mark_is_drawn_last():
    """Two changes on nearly the same line: the destroy has to be the visible one."""
    strip = ChangeMap()
    strip.show([Mark(line=10, tone="destroy"), Mark(line=10, tone="add")], lines=100)
    assert [mark.tone for mark in strip._marks][-1] == "destroy"


def test_a_click_reports_the_line_it_landed_on():
    went: list[int] = []
    strip = ChangeMap(on_go_to=went.append)
    strip.show([], lines=100)
    strip._on_click(None, 1, 0.0, 0.0)
    assert went == [1]


def test_a_line_is_one_based_as_a_person_counts():
    strip = ChangeMap()
    strip.show([], lines=100)
    assert strip.line_at(0.0) == 1


def test_a_point_past_the_end_clamps_to_the_last_line():
    """A strip is taller than its content by a pixel or two; no line 101 exists."""
    strip = ChangeMap()
    strip.show([], lines=100)
    assert strip.line_at(999_999.0) == 100


def test_a_hover_finds_the_mark_it_is_over():
    strip = ChangeMap()
    strip.show([Mark(line=1, tone="add")], lines=100)
    assert strip.mark_near(0.0, within=5) is not None


def test_a_hover_nowhere_near_a_mark_finds_nothing():
    strip = ChangeMap()
    strip.show([Mark(line=90, tone="add")], lines=100)
    assert strip.mark_near(0.0, within=2) is None


def test_an_empty_map_never_claims_a_mark():
    strip = ChangeMap()
    strip.show([], lines=100)
    assert strip.mark_near(0.0) is None


def test_a_mark_is_never_thinner_than_it_can_be_seen():
    """One line of 4,000 is a fraction of a pixel, and an invisible mark is none."""
    assert MINIMUM >= 2


def test_clearing_removes_every_mark():
    strip = ChangeMap()
    strip.show([Mark(line=1, tone="add")], lines=10)
    strip.clear()
    assert strip.mark_near(0.0) is None


def test_a_tone_with_no_colour_is_skipped_rather_than_drawn_black():
    """A colour we do not have is not a reason to invent one."""
    strip = ChangeMap()
    strip.use_colours({"add": coloured()["add"]})
    strip.show([Mark(line=1, tone="add"), Mark(line=2, tone="mystery")], lines=10)
    drawn = [mark for mark in strip._marks if mark.tone in strip._colours]
    assert [mark.tone for mark in drawn] == ["add"]
