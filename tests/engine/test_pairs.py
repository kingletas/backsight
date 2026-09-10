"""Auto-closing brackets, and the cases where closing is the wrong answer."""

from __future__ import annotations

import pytest

from backsight.engine.text.pairs import typed, wrapping


@pytest.mark.parametrize(("opener", "closer"), [("(", ")"), ("[", "]"), ("{", "}")])
def test_a_bracket_closes_itself_at_the_end_of_a_line(opener, closer):
    assert typed(opener, before="  input = ", after="").insert == closer


def test_and_before_whitespace_or_another_closer():
    assert typed("(", before="x", after=" ").insert == ")"
    assert typed("(", before="x", after=")").insert == ")"


def test_but_not_when_a_word_follows():
    """Typing `(` before a token almost always means wrapping it."""
    assert typed("(", before="", after="var.name").is_nothing


def test_typing_the_closer_that_is_there_moves_over_it():
    """Adding a second one is what makes it feel like nothing happened."""
    said = typed(")", before="max(", after=")")
    assert said.step_over
    assert not said.insert


def test_a_closer_with_nothing_after_it_is_just_a_character():
    assert typed(")", before="max(1", after="").is_nothing


def test_a_quote_opens_a_string_at_the_end_of_a_line():
    assert typed('"', before="  input = ", after="").insert == '"'


def test_the_second_quote_of_a_string_does_not_open_another():
    said = typed('"', before='  input = "one', after="")
    assert not said.insert


def test_an_escaped_quote_never_opens_anything():
    assert typed('"', before='  input = "a\\\\', after="").is_nothing


def test_a_quote_before_a_word_is_not_an_opening():
    assert typed('"', before="", after="already").is_nothing


def test_an_ordinary_character_does_nothing():
    assert typed("a", before="", after="").is_nothing


def test_a_selection_gets_wrapped_rather_than_replaced():
    """The one case where typing over a selection should not delete it."""
    assert wrapping('"', "var.name") == '"var.name"'
    assert wrapping("(", "a + b") == "(a + b)"


def test_wrapping_needs_both_a_pair_and_a_selection():
    assert wrapping("a", "x") == ""
    assert wrapping("(", "") == ""


def test_a_step_over_says_which_character_it_is_stepping_over():
    """So the caller can check before deleting anything."""
    assert typed(")", before="max(", after=")").character == ")"
