"""Diagnostics said in the reader's language, against real captured output."""

from __future__ import annotations

from pathlib import Path

import pytest

from backsight.engine.plan.diagnostics import errors
from backsight.engine.plan.repair import RULES, explain

CAPTURES = Path(__file__).resolve().parents[2] / "fixtures" / "plan-failures"


def captured(name: str) -> str:
    return (CAPTURES / f"{name}.out").read_text(encoding="utf-8")


def only(name: str):
    found = errors(captured(name))
    assert len(found) == 1, f"{name} captured {len(found)} errors"
    return found[0]


QUOTED = 'variable "tags" {\n  type = "map"\n}\n'


def test_every_rule_is_backed_by_a_capture():
    """A rule written from memory fires on output nobody has seen."""
    summaries = set()
    for capture in CAPTURES.glob("*.out"):
        summaries |= {found.summary for found in errors(capture.read_text())}
    assert set(RULES) <= summaries, set(RULES) - summaries


def test_the_title_is_rewritten_not_the_engines_first_line():
    found = only("quoted-type-constraint")
    said = explain(found, QUOTED)
    assert said.title == "Type constraint is quoted"
    assert said.title != found.summary


def test_the_quoted_type_fix_is_the_line_with_the_quotes_taken_off():
    said = explain(only("quoted-type-constraint"), QUOTED)
    assert said.is_fixable
    assert said.repair.line == 2
    assert said.repair.before == '  type = "map"'
    assert said.repair.after == "  type = map(string)"


def test_the_fix_keeps_the_indentation_it_found():
    source = 'variable "tags" {\n\t\ttype = "list"\n}\n'
    said = explain(only("quoted-type-constraint"), source)
    assert said.repair.after == "\t\ttype = list(string)"


def test_a_fix_is_not_offered_when_the_line_is_not_what_was_described():
    """The buffer may have moved on since the plan ran."""
    said = explain(only("quoted-type-constraint"), "# someone edited this\n# and this\n")
    assert not said.is_fixable


def test_a_fix_is_not_offered_without_the_source():
    assert not explain(only("quoted-type-constraint")).is_fixable


@pytest.mark.parametrize(
    ("capture", "title", "says"),
    [
        ("missing-required-argument", "A required argument is missing", "value"),
        ("unsupported-argument", "That argument is not recognised", "nonsense"),
        ("undeclared-variable", "A variable is used but never declared", "missing"),
    ],
)
def test_it_names_what_the_engine_named(capture, title, says):
    said = explain(only(capture))
    assert said.title == title
    assert says in said.explanation


@pytest.mark.parametrize(
    "capture", ["missing-required-argument", "unsupported-argument", "undeclared-variable"]
)
def test_nothing_is_offered_where_the_value_is_the_users_to_choose(capture):
    """Inserting a placeholder is a guess wearing the costume of a fix."""
    assert not explain(only(capture)).is_fixable


def test_an_unrecognised_diagnostic_keeps_the_engines_own_words():
    from backsight.engine.plan.diagnostics import Diagnostic

    found = Diagnostic(severity="Error", summary="Something new", detail="a body")
    said = explain(found)
    assert said.title == "Something new"
    assert said.explanation == "a body"
    assert not said.is_fixable
