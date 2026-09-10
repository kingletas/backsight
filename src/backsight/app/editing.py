"""Line operations, applied to a live buffer.

The decisions are all in `engine/text/lines.py`, which is pure text and tested
without a window. This only works out which lines are selected, hands them over,
and puts the selection back where the operation says it went.

Each one is a single user action, so undo takes the whole thing back rather than
line by line.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import GtkSource

from backsight.engine.text import lines as ops
from backsight.engine.text.lines import Span

Operation = Callable[[str, Span], tuple[str, Span]]

# What the menu and the palette offer, in the order the design's Edit menu lists.
OPERATIONS: dict[str, Operation] = {
    "duplicate-lines": ops.duplicate,
    "delete-lines": ops.delete,
    "join-lines": ops.join_lines,
    "move-lines-up": lambda text, span: ops.move(text, span, by=-1),
    "move-lines-down": lambda text, span: ops.move(text, span, by=1),
    "swap-lines": ops.swap,
    "sort-lines": ops.sort,
    "sort-lines-case-sensitive": lambda text, span: ops.sort(text, span, case_sensitive=True),
    "reverse-lines": ops.reverse,
    "unique-lines": ops.unique,
    "shuffle-lines": ops.shuffle,
    "toggle-line-comment": ops.toggle_line_comment,
    "toggle-block-comment": ops.toggle_block_comment,
}


def selected_span(buffer: GtkSource.Buffer) -> Span:
    """The whole lines the selection touches, or the line the cursor is on."""
    # Empty tuple when nothing is selected, a pair when something is — not a
    # found flag followed by two iterators.
    bounds = buffer.get_selection_bounds()
    if not bounds:
        where = buffer.get_iter_at_mark(buffer.get_insert())
        return Span(first=where.get_line(), last=where.get_line())
    start, end = bounds
    last = end.get_line()
    # A selection ending at column zero has not really reached that line.
    if end.get_line_offset() == 0 and last > start.get_line():
        last -= 1
    return Span(first=start.get_line(), last=last)


def apply(buffer: GtkSource.Buffer, operation: Operation) -> None:
    """Runs one operation over the selection and restores it afterwards."""
    before = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
    span = selected_span(buffer)
    after, moved = operation(before, span)
    if after == before:
        return

    # Only the part that differs is rewritten. Replacing the whole buffer would
    # also work and would touch every character of a file the user did not ask
    # to change — and `set_text` inside a user action fights GtkSourceView's own
    # irreversible action.
    start, end = _differing_range(before, after)
    buffer.begin_user_action()
    # `get_iter_at_offset` returns a bare iterator; `get_iter_at_line` returns a
    # pair. Same API, two conventions.
    from_iter = buffer.get_iter_at_offset(start)
    to_iter = buffer.get_iter_at_offset(len(before) - end)
    buffer.delete(from_iter, to_iter)
    buffer.insert(buffer.get_iter_at_offset(start), after[start : len(after) - end])
    buffer.end_user_action()
    _select(buffer, moved)


def replace_whole(buffer: GtkSource.Buffer, after: str) -> bool:
    """Rewrites a buffer to new content, touching only what differs.

    Whole-file conversions go through here for the same reason line operations
    do: `set_text` inside a user action fights GtkSourceView's own irreversible
    action, and rewriting every character marks a file as changed in places
    nobody changed.
    """
    before = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
    if after == before:
        return False
    start, end = _differing_range(before, after)
    buffer.begin_user_action()
    from_iter = buffer.get_iter_at_offset(start)
    to_iter = buffer.get_iter_at_offset(len(before) - end)
    buffer.delete(from_iter, to_iter)
    buffer.insert(buffer.get_iter_at_offset(start), after[start : len(after) - end])
    buffer.end_user_action()
    return True


def _differing_range(before: str, after: str) -> tuple[int, int]:
    """How much of each end is identical, so only the middle is rewritten."""
    limit = min(len(before), len(after))
    head = 0
    while head < limit and before[head] == after[head]:
        head += 1
    tail = 0
    while tail < limit - head and before[-1 - tail] == after[-1 - tail]:
        tail += 1
    return head, tail


def run(buffer: GtkSource.Buffer, name: str) -> bool:
    """Runs an operation by the name the menu and the palette use."""
    operation = OPERATIONS.get(name)
    if operation is None:
        return False
    apply(buffer, operation)
    return True


def _select(buffer: GtkSource.Buffer, span: Span) -> None:
    total = buffer.get_line_count() - 1
    first_ok, start = buffer.get_iter_at_line(min(span.first, total))
    last_ok, end = buffer.get_iter_at_line(min(span.last, total))
    if not (first_ok and last_ok):
        return
    if not end.ends_line():
        end.forward_to_line_end()
    buffer.select_range(start, end)
