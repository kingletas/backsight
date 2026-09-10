"""Line operations against a real buffer, and the selection they leave behind."""

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("GtkSource", "5")

from gi.repository import GtkSource  # noqa: E402

from backsight.app.editing import OPERATIONS, run, selected_span  # noqa: E402
from backsight.engine.text.lines import Span  # noqa: E402

FILE = "alpha\nbravo\ncharlie\ndelta\n"


def buffer_with(text: str = FILE) -> GtkSource.Buffer:
    buffer = GtkSource.Buffer()
    buffer.set_text(text)
    return buffer


def text_of(buffer) -> str:
    return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)


def select(buffer, first: int, last: int) -> None:
    _ok, start = buffer.get_iter_at_line(first)
    _ok, end = buffer.get_iter_at_line(last)
    end.forward_to_line_end()
    buffer.select_range(start, end)


def test_with_no_selection_the_span_is_the_cursor_line():
    buffer = buffer_with()
    _ok, where = buffer.get_iter_at_line(2)
    buffer.place_cursor(where)
    assert selected_span(buffer) == Span(2, 2)


def test_a_selection_covers_the_lines_it_touches():
    buffer = buffer_with()
    select(buffer, 1, 2)
    assert selected_span(buffer) == Span(1, 2)


def test_a_selection_ending_at_column_zero_has_not_reached_that_line():
    """Dragging down to the start of a line selects the lines above it."""
    buffer = buffer_with()
    _ok, start = buffer.get_iter_at_line(1)
    _ok, end = buffer.get_iter_at_line(3)
    buffer.select_range(start, end)
    assert selected_span(buffer) == Span(1, 2)


def test_an_operation_runs_over_the_selection():
    buffer = buffer_with()
    select(buffer, 1, 1)
    assert run(buffer, "duplicate-lines")
    assert text_of(buffer) == "alpha\nbravo\nbravo\ncharlie\ndelta\n"


def test_the_selection_follows_the_operation():
    buffer = buffer_with()
    select(buffer, 1, 1)
    run(buffer, "duplicate-lines")
    assert selected_span(buffer) == Span(2, 2)


def test_one_operation_is_one_undo():
    """Not one per line. An undo that half-undoes is worse than none."""
    buffer = buffer_with()
    buffer.set_enable_undo(True)
    select(buffer, 0, 3)
    run(buffer, "sort-lines")
    assert text_of(buffer).splitlines()[0] == "alpha"
    run(buffer, "reverse-lines")
    assert text_of(buffer).splitlines()[0] == "delta"
    buffer.undo()
    assert text_of(buffer).splitlines()[0] == "alpha"


def test_an_operation_that_changes_nothing_writes_nothing():
    buffer = buffer_with()
    buffer.set_enable_undo(True)
    select(buffer, 0, 0)
    run(buffer, "swap-lines")
    assert buffer.get_can_undo() is False


def test_an_unknown_operation_is_refused_rather_than_ignored():
    assert run(buffer_with(), "invented-operation") is False


@pytest.mark.parametrize("name", sorted(OPERATIONS))
def test_every_offered_operation_runs(name):
    """Deleting every line leaves an empty buffer, which is a result."""
    buffer = buffer_with()
    select(buffer, 0, 3)
    assert run(buffer, name) is True


def test_only_the_part_that_differs_is_rewritten():
    """A file the user did not ask to change keeps its every character."""
    buffer = buffer_with("keep\nalpha\nbravo\nkeep too\n")
    marks = buffer.create_mark("watch", buffer.get_start_iter(), True)
    select(buffer, 1, 2)
    run(buffer, "reverse-lines")
    assert text_of(buffer) == "keep\nbravo\nalpha\nkeep too\n"
    # A mark before the edit is undisturbed, which set_text would have dropped.
    assert buffer.get_iter_at_mark(marks).get_offset() == 0
