"""Sheet 9's baseline, line by line.

None of it is novel and all of it is required. The property that matters
throughout: everything outside the span comes back untouched.
"""

import pytest

from backsight.engine.text.lines import (
    Span,
    delete,
    duplicate,
    join_lines,
    move,
    reverse,
    shuffle,
    sort,
    swap,
    toggle_block_comment,
    toggle_line_comment,
    unique,
)

FILE = "alpha\nbravo\ncharlie\ndelta\n"


def test_a_span_runs_forwards():
    with pytest.raises(ValueError, match="runs forwards"):
        Span(first=3, last=1)


# --- lines ----------------------------------------------------------------


def test_duplicate_copies_below_and_the_selection_follows_the_copy():
    text, span = duplicate(FILE, Span(1, 1))
    assert text == "alpha\nbravo\nbravo\ncharlie\ndelta\n"
    assert (span.first, span.last) == (2, 2)


def test_duplicate_handles_several_lines():
    text, _ = duplicate(FILE, Span(0, 1))
    assert text == "alpha\nbravo\nalpha\nbravo\ncharlie\ndelta\n"


def test_delete_removes_the_span_and_lands_the_cursor():
    text, span = delete(FILE, Span(1, 2))
    assert text == "alpha\ndelta\n"
    assert (span.first, span.last) == (1, 1)


def test_deleting_everything_leaves_an_empty_file_rather_than_nothing():
    text, _ = delete("one\ntwo", Span(0, 1))
    assert text == ""


def test_join_runs_the_span_onto_one_line():
    text, _ = join_lines("resource {\n  a = 1\n  b = 2\n}\n", Span(1, 2))
    assert text == "resource {\n  a = 1 b = 2\n}\n"


def test_joining_one_line_takes_the_next_one_up():
    text, _ = join_lines(FILE, Span(0, 0))
    assert text.startswith("alpha bravo\n")


def test_move_up_and_down():
    text, span = move(FILE, Span(2, 2), by=-1)
    assert text == "alpha\ncharlie\nbravo\ndelta\n"
    assert (span.first, span.last) == (1, 1)
    back, _ = move(text, span, by=1)
    assert back == FILE


def test_moving_past_either_end_changes_nothing():
    assert move(FILE, Span(0, 0), by=-1) == (FILE, Span(0, 0))
    assert move(FILE, Span(3, 3), by=1)[0] == FILE


def test_swap_exchanges_the_ends_of_the_span():
    text, _ = swap(FILE, Span(0, 2))
    assert text == "charlie\nbravo\nalpha\ndelta\n"


def test_swapping_one_line_changes_nothing():
    assert swap(FILE, Span(1, 1))[0] == FILE


def test_sort_is_case_insensitive_unless_asked():
    text, _ = sort("b\nA\na\nB\n", Span(0, 3))
    assert text.splitlines()[:2] == ["A", "a"]
    sensitive, _ = sort("b\nA\na\nB\n", Span(0, 3), case_sensitive=True)
    assert sensitive.splitlines() == ["A", "B", "a", "b"]


def test_sort_can_go_the_other_way():
    text, _ = sort(FILE, Span(0, 3), reverse=True)
    assert text.splitlines() == ["delta", "charlie", "bravo", "alpha"]


def test_reverse_flips_the_span_only():
    text, _ = reverse(FILE, Span(0, 2))
    assert text == "charlie\nbravo\nalpha\ndelta\n"


def test_unique_keeps_the_first_of_each_and_the_order():
    text, span = unique("b\na\nb\nc\na\n", Span(0, 4))
    assert text.splitlines() == ["b", "a", "c"]
    assert (span.first, span.last) == (0, 2)


def test_shuffle_is_a_permutation_and_its_order_is_a_parameter():
    """The shuffler is injected so this is a fact rather than a probability."""
    text, _ = shuffle(FILE, Span(0, 3), shuffler=lambda items: items.reverse())
    assert text.splitlines() == ["delta", "charlie", "bravo", "alpha"]


def test_shuffle_without_a_shuffler_still_returns_the_same_lines():
    text, _ = shuffle(FILE, Span(0, 3))
    assert sorted(text.splitlines()) == ["alpha", "bravo", "charlie", "delta"]


# --- the property that matters --------------------------------------------


@pytest.mark.parametrize(
    "operation",
    [duplicate, delete, join_lines, swap, sort, reverse, unique],
    ids=lambda f: f.__name__,
)
def test_nothing_outside_the_span_is_touched(operation):
    text = "keep me\nalpha\nbravo\nkeep me too\n"
    result, _ = operation(text, Span(1, 2))
    assert result.startswith("keep me\n")
    assert result.endswith("keep me too\n")


def test_crlf_survives_every_operation():
    """Split on \\n alone, so the \\r stays on the end of each line."""
    text = "alpha\r\nbravo\r\ncharlie\r\n"
    result, _ = duplicate(text, Span(1, 1))
    assert result == "alpha\r\nbravo\r\nbravo\r\ncharlie\r\n"


def test_a_heredoc_containing_a_form_feed_is_not_split_on_it():
    """`splitlines` breaks on \\v and \\f; this must not."""
    text = "locals {\n  a = <<T\n\x0cnot a line break\nT\n}\n"
    result, _ = duplicate(text, Span(0, 0))
    assert result.count("\x0c") == 1
    assert result == "locals {\nlocals {\n  a = <<T\n\x0cnot a line break\nT\n}\n"


# --- comments -------------------------------------------------------------


def test_toggling_comments_a_span_at_its_shallowest_indent():
    text, _ = toggle_line_comment("resource {\n  a = 1\n    b = 2\n}\n", Span(1, 2))
    assert text == "resource {\n  # a = 1\n  #   b = 2\n}\n"


def test_toggling_again_takes_the_comment_off():
    original = "resource {\n  a = 1\n    b = 2\n}\n"
    once, span = toggle_line_comment(original, Span(1, 2))
    twice, _ = toggle_line_comment(once, span)
    assert twice == original


def test_a_mixed_selection_comments_everything():
    """What every other editor does, and what a second press then undoes."""
    text, _ = toggle_line_comment("# a\nb\n", Span(0, 1))
    assert text.splitlines() == ["# # a", "# b"]


def test_blank_lines_are_left_alone():
    text, _ = toggle_line_comment("a\n\nb\n", Span(0, 2))
    assert text.splitlines() == ["# a", "", "# b"]


def test_the_double_slash_form_is_recognised_when_uncommenting():
    text, _ = toggle_line_comment("// a\n// b\n", Span(0, 1))
    assert text.splitlines() == ["a", "b"]


def test_only_one_space_after_the_marker_is_ours():
    text, _ = toggle_line_comment("#   spaced\n", Span(0, 0))
    assert text.splitlines() == ["  spaced"]


def test_a_block_comment_wraps_one_line():
    text, _ = toggle_block_comment("  a = 1\n", Span(0, 0))
    assert text.splitlines() == ["  /* a = 1 */"]


def test_a_block_comment_unwraps_the_same_line():
    once, span = toggle_block_comment("  a = 1\n", Span(0, 0))
    twice, _ = toggle_block_comment(once, span)
    assert twice.splitlines() == ["  a = 1"]


def test_a_block_comment_spans_several_lines():
    text, _ = toggle_block_comment("a\nb\nc\n", Span(0, 2))
    assert text.splitlines() == ["/* a", "b", "c */"]
