"""What happens to a file's text when it is saved."""

from __future__ import annotations

from backsight.engine.text.handling import ensure_final_newline, on_save, trim_trailing_whitespace


def test_trailing_spaces_go():
    assert trim_trailing_whitespace("a  \nb\t\n") == "a\nb\n"


def test_a_file_gains_the_newline_every_other_tool_assumes():
    assert ensure_final_newline("a\nb") == "a\nb\n"


def test_one_that_already_has_it_is_untouched():
    assert ensure_final_newline("a\n") == "a\n"


def test_an_empty_file_stays_empty():
    """A newline in a file nobody has written in is a change nobody asked for."""
    assert ensure_final_newline("") == ""


def test_trimming_runs_first():
    """Adding the newline first would leave the trailing spaces forever."""
    assert on_save("a\nb   ") == "a\nb\n"


def test_each_half_can_be_turned_off():
    assert on_save("a\nb   ", final_newline=False) == "a\nb"
    assert on_save("a\nb   ", trim=False) == "a\nb   \n"
    assert on_save("a\nb   ", trim=False, final_newline=False) == "a\nb   "


def test_neither_can_change_what_the_file_means():
    """Which is why both are on by default and everything else here is not."""
    source = 'resource "a" "b" {\n  input = <<-EOT\n    keep   me   \n  EOT\n}'
    assert on_save(source).replace("\n", "") != source.replace("\n", "")  # trailing spaces went
    assert "keep   me" in on_save(source)
