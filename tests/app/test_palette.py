"""The palette never opens empty, and Enter acts on the best match."""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.palette import Palette  # noqa: E402
from backsight.engine.presentation.palette import Entry, Kind  # noqa: E402

FILES = [Entry("main.tf", Kind.FILE), Entry("variables.tf", Kind.FILE)]
RESOURCES = [Entry("aws_instance.api", Kind.RESOURCE, detail="main.tf:10")]
COMMANDS = [Entry("Convergence: run", Kind.COMMAND, action="convergence-run")]
SUGGESTIONS = [Entry("Plan", Kind.COMMAND, action="plan")]
EVERYTHING = FILES + RESOURCES + COMMANDS


def test_it_opens_with_suggestions_rather_than_a_blank_list():
    palette = Palette(EVERYTHING, SUGGESTIONS)
    assert [entry.label for entry in palette.shown] == ["Plan"]


def test_typing_a_prefix_switches_what_is_searched():
    palette = Palette(EVERYTHING, SUGGESTIONS)
    palette.entry.set_text("@api")
    assert [entry.label for entry in palette.shown][0] == "aws_instance.api"


def test_suggestions_survive_a_search():
    palette = Palette(EVERYTHING, SUGGESTIONS)
    palette.entry.set_text(">conv")
    assert "Plan" in [entry.label for entry in palette.shown]


def test_enter_acts_on_the_first_match_not_on_a_heading():
    chosen: list[Entry] = []
    palette = Palette(EVERYTHING, SUGGESTIONS, on_choose=chosen.append)
    palette.entry.set_text("main")
    palette.choose()
    assert chosen and chosen[0].label == "main.tf"


def test_choosing_with_nothing_shown_does_nothing():
    chosen: list[Entry] = []
    palette = Palette([], [], on_choose=chosen.append)
    palette.entry.set_text(":abc")
    palette.choose()
    assert chosen == []


def test_a_line_number_can_be_chosen():
    chosen: list[Entry] = []
    palette = Palette(EVERYTHING, SUGGESTIONS, on_choose=chosen.append)
    palette.entry.set_text(":42")
    palette.choose()
    assert chosen and chosen[0].label == "Line 42"
    assert chosen[0].action == "goto-line"


def test_a_query_matching_nothing_still_offers_the_suggestions():
    palette = Palette(EVERYTHING, SUGGESTIONS)
    palette.entry.set_text(">zzzzz")
    assert [entry.label for entry in palette.shown] == ["Plan"]


# --- problems, the sixth prefix -------------------------------------------


def test_the_problems_prefix_is_a_chip():
    """`!` was specified and never built, so the capability the Problems tab
    used to carry had no keyboard route at all."""
    from backsight.app.palette import PREFIXES

    assert ("!", "problems") in PREFIXES


def test_a_problem_is_matched_by_its_own_prefix():
    from backsight.engine.presentation import palette as source

    entries = [
        source.Entry(
            label="argument is not expected here", kind=source.Kind.PROBLEM, detail="main.tf:12"
        ),
        source.Entry(label="main.tf", kind=source.Kind.FILE),
    ]
    found = source.results(entries, [], "!argument")
    assert [one.label for one in found.matches] == ["argument is not expected here"]
    assert found.heading == "Problems"


def test_a_plan_with_no_problems_shows_the_suggestions_rather_than_nothing():
    from backsight.engine.presentation import palette as source

    found = source.results([], [source.Entry(label="Plan", kind=source.Kind.COMMAND)], "!")
    assert not found.matches
    assert found.suggestions
