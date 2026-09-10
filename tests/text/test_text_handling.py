"""Indentation, line endings and whitespace — each an explicit act.

Every one of these rewrites a file wholesale, which is what FR-ED-07 forbids
doing on somebody's behalf. So they are actions, and the tests are mostly about
what they leave alone.
"""

import pytest

from backsight.engine.text.handling import (
    Indentation,
    LineEnding,
    convert_indentation,
    convert_line_endings,
    decode,
    detect_indentation,
    detect_line_ending,
    encodings,
    is_mixed,
    trim_trailing_whitespace,
)

# --- line endings ---------------------------------------------------------


def test_the_ending_a_file_uses_is_read_rather_than_assumed():
    assert detect_line_ending("a\nb\n") is LineEnding.LF
    assert detect_line_ending("a\r\nb\r\n") is LineEnding.CRLF


def test_a_mixed_file_is_worth_saying_out_loud():
    assert is_mixed("a\r\nb\n") is True
    assert is_mixed("a\nb\n") is False


def test_a_mixed_file_keeps_its_majority():
    assert detect_line_ending("a\r\nb\r\nc\n") is LineEnding.CRLF


def test_converting_endings_round_trips():
    original = "a\nb\nc\n"
    crlf = convert_line_endings(original, LineEnding.CRLF)
    assert crlf == "a\r\nb\r\nc\r\n"
    assert convert_line_endings(crlf, LineEnding.LF) == original


def test_converting_a_mixed_file_makes_it_consistent():
    assert convert_line_endings("a\r\nb\n", LineEnding.LF) == "a\nb\n"


# --- indentation ----------------------------------------------------------


def test_indentation_is_read_from_the_file_and_not_from_a_setting():
    """Inserting spaces into somebody's tab-indented module is real damage."""
    assert detect_indentation("resource {\n\ta = 1\n}\n").uses_tabs is True
    assert detect_indentation("resource {\n  a = 1\n}\n").uses_tabs is False


def test_the_indent_width_is_the_step_between_levels():
    text = "a {\n  b {\n    c = 1\n  }\n}\n"
    assert detect_indentation(text).width == 2


def test_a_file_with_no_indentation_falls_back_to_the_default():
    assert detect_indentation("a\nb\n", default_width=4).width == 4


def test_converting_indentation_touches_only_the_leading_whitespace():
    text = 'a {\n  b = "  keep  these  "\n}\n'
    converted = convert_indentation(text, to_tabs=True, width=2)
    assert converted == 'a {\n\tb = "  keep  these  "\n}\n'


def test_converting_back_returns_the_original():
    text = "a {\n  b {\n    c = 1\n  }\n}\n"
    tabs = convert_indentation(text, to_tabs=True, width=2)
    assert convert_indentation(tabs, to_tabs=False, width=2) == text


def test_the_label_says_what_the_status_bar_shows():
    assert Indentation(uses_tabs=False, width=2).label == "Spaces: 2"
    assert Indentation(uses_tabs=True, width=4).label == "Tabs"


# --- whitespace -----------------------------------------------------------


def test_trailing_whitespace_is_trimmed_from_every_line():
    assert trim_trailing_whitespace("a   \nb\t\n") == "a\nb\n"


def test_trimming_leaves_the_final_newline_alone():
    assert trim_trailing_whitespace("a\n") == "a\n"
    assert trim_trailing_whitespace("a") == "a"


def test_trimming_does_not_touch_leading_whitespace():
    assert trim_trailing_whitespace("  a  \n") == "  a\n"


# --- encoding -------------------------------------------------------------


def test_reopening_with_an_encoding_reads_what_utf8_refused():
    """The latin-1 file the editor refuses can be opened deliberately."""
    data = "café".encode("latin-1")
    with pytest.raises(UnicodeDecodeError):
        data.decode("utf-8")
    assert decode(data, "latin-1") == "café"


def test_the_offered_encodings_are_a_short_list():
    assert "utf-8" == encodings()[0]
    assert len(encodings()) <= 8
