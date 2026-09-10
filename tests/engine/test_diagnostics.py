"""The engine's own errors, read from output it really produced.

Captured in `fixtures/plan-failures/`. The panel used to say "the plan failed;
the output says why" and show the output nowhere, which admits an explanation
exists and withholds it.
"""

from __future__ import annotations

from pathlib import Path

from backsight.engine.plan.diagnostics import errors, needs_initialising, read, summarise

CAPTURES = Path(__file__).resolve().parents[2] / "fixtures" / "plan-failures"


def output(name: str) -> str:
    return (CAPTURES / f"{name}.out").read_text()


def test_an_error_is_read_with_its_own_words():
    found = read(output("undeclared-variable"))
    assert len(found) == 1
    assert found[0].severity == "Error"
    assert found[0].summary == "Reference to undeclared input variable"
    assert "has not been declared" in found[0].detail


def test_the_location_is_kept_so_somebody_can_go_there():
    assert read(output("undeclared-variable"))[0].where == "main.tf:2"


def test_the_quoted_source_is_left_out_of_the_detail():
    """The editor is already showing that file."""
    detail = read(output("undeclared-variable"))[0].detail
    assert "2:   input = var.missing" not in detail
    assert "on main.tf line 2" not in detail


def test_the_box_drawing_is_not_part_of_the_message():
    for found in read(output("undeclared-variable")):
        assert "│" not in found.detail
        assert "╷" not in found.summary


def test_an_uninitialised_workspace_is_recognised():
    """The first failure almost everybody meets, and one command fixes it."""
    assert needs_initialising(output("not-initialised"))
    assert not needs_initialising(output("undeclared-variable"))


def test_the_summary_names_what_went_wrong():
    assert summarise(output("not-initialised")) == "Inconsistent dependency lock file"
    assert summarise(output("undeclared-variable")).startswith("Reference to undeclared")


def test_more_than_one_error_says_how_many_more():
    doubled = output("undeclared-variable") + output("not-initialised")
    assert "and 1 more" in summarise(doubled)


def test_output_in_a_shape_this_does_not_know_is_not_guessed_at():
    """Never invent a reason. The raw text is still there to read."""
    assert summarise("something went wrong in a way nobody parsed") == ""
    assert read("") == []


def test_a_warning_is_not_an_error():
    text = "Warning: Deprecated attribute\n\nUse the other one.\n"
    assert read(text)[0].severity == "Warning"
    assert errors(text) == []
    assert summarise(text) == ""
