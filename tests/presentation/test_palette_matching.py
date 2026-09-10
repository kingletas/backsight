"""Sheet 4: the palette opens with suggestions and never an empty prompt."""

from __future__ import annotations

from backsight.engine.presentation.palette import (
    Entry,
    Kind,
    parse,
    rank,
    results,
    score,
)

FILES = [
    Entry("main.tf", Kind.FILE),
    Entry("modules/net/main.tf", Kind.FILE),
    Entry("variables.tf", Kind.FILE),
]
RESOURCES = [
    Entry("aws_instance.api", Kind.RESOURCE, detail="main.tf:10"),
    Entry("aws_instance.worker", Kind.RESOURCE, detail="compute.tf:4"),
    Entry("data.aws_instance.existing", Kind.RESOURCE, detail="imports.tf:8"),
]
COMMANDS = [
    Entry("Convergence: run", Kind.COMMAND, action="convergence-run"),
    Entry("Convergence: show coverage", Kind.COMMAND, action="convergence-coverage"),
    Entry("Config: edit stack definition", Kind.COMMAND, action="edit-stack"),
]
SUGGESTIONS = [
    Entry("Plan", Kind.COMMAND, action="plan"),
    Entry("Scaffold from catalog…", Kind.COMMAND, action="scaffold"),
]
EVERYTHING = FILES + RESOURCES + COMMANDS


def labels(entries) -> list[str]:
    return [entry.label for entry in entries]


def test_no_prefix_searches_files():
    assert parse("main").kind is Kind.FILE
    assert parse("main").term == "main"


def test_each_prefix_selects_its_own_source():
    assert parse("@aws").kind is Kind.RESOURCE
    assert parse(":42").kind is Kind.LINE
    assert parse("#aws_instance").kind is Kind.DOCUMENTATION
    assert parse(">con").kind is Kind.COMMAND


def test_the_prefix_is_not_part_of_the_search_term():
    assert parse("@aws_instance.api").term == "aws_instance.api"


def test_a_prefix_alone_is_an_empty_query_of_that_kind():
    query = parse(">")
    assert query.kind is Kind.COMMAND
    assert query.is_empty


def test_an_empty_palette_shows_suggestions_rather_than_nothing():
    """A blank palette is a wall for anyone who writes Terraform monthly."""
    shown = results(EVERYTHING, SUGGESTIONS, ">")
    assert shown.matches == []
    assert labels(shown.suggestions) == ["Plan", "Scaffold from catalog…"]
    assert not shown.is_empty


def test_suggestions_stay_below_matches_and_are_never_removed():
    shown = results(EVERYTHING, SUGGESTIONS, ">con")
    assert labels(shown.matches)[0].startswith("Convergence")
    assert shown.suggestions == SUGGESTIONS


def test_a_suggestion_that_is_already_a_match_is_not_listed_twice():
    suggestions = [Entry("Convergence: run", Kind.COMMAND, action="convergence-run")]
    shown = results(EVERYTHING, suggestions, ">conv")
    assert shown.suggestions == []


def test_a_query_only_searches_its_own_kind():
    shown = results(EVERYTHING, [], "@aws")
    assert all(entry.kind is Kind.RESOURCE for entry in shown.matches)
    assert "main.tf" not in labels(shown.matches)


def test_a_prefix_match_beats_a_word_match_beats_a_subsequence():
    entries = [
        Entry("zzz api zzz", Kind.FILE),
        Entry("api.tf", Kind.FILE),
        Entry("a_p_i.tf", Kind.FILE),
    ]
    assert labels(rank(entries, parse("api")))[0] == "api.tf"
    assert labels(rank(entries, parse("api")))[1] == "zzz api zzz"


def test_a_shorter_label_wins_an_otherwise_equal_match():
    entries = [Entry("main.tf.backup", Kind.FILE), Entry("main.tf", Kind.FILE)]
    assert labels(rank(entries, parse("main")))[0] == "main.tf"


def test_a_resource_address_is_matched_by_any_of_its_parts():
    """The address is the symbol table, so its words have to be reachable."""
    assert labels(rank(RESOURCES, parse("@api")))[0] == "aws_instance.api"
    assert labels(rank(RESOURCES, parse("@worker")))[0] == "aws_instance.worker"


def test_a_line_number_is_offered_as_itself():
    shown = results([], [], ":42")
    assert labels(shown.matches) == ["Line 42"]


def test_something_that_is_not_a_line_number_offers_nothing():
    """A line query either is one or it is not; guessing helps nobody."""
    assert results([], [], ":abc").matches == []
    assert results([], [], ":0").matches == []


def test_a_line_query_shows_no_suggestions():
    """Nothing else is a plausible answer to a line number."""
    assert results(EVERYTHING, SUGGESTIONS, ":42").suggestions == []


def test_matching_ignores_case():
    assert score("Convergence: run", "CONV") is not None
    assert labels(rank(COMMANDS, parse(">CONVERGENCE")))


def test_a_query_matching_nothing_still_shows_suggestions():
    shown = results(EVERYTHING, SUGGESTIONS, ">zzzzzz")
    assert shown.matches == []
    assert shown.suggestions == SUGGESTIONS
    assert not shown.is_empty


def test_leading_space_does_not_change_the_prefix():
    assert parse("  >plan").kind is Kind.COMMAND


def test_every_kind_has_a_heading():
    from backsight.engine.presentation.palette import HEADINGS

    assert set(HEADINGS) == set(Kind)
