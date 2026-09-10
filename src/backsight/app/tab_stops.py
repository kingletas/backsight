"""Tab stops in the buffer, because the toolkit's own cannot hold Terraform.

`GtkSource.Snippet` parses `${1:default}` and would have done all of this — and
it eats the opening brace of every HCL interpolation, with no escape that
round-trips. See `docs/findings/014`.

So this places the text, leaves a `Gtk.TextMark` pair at each stop, and moves
between them on Tab. Marks are the reason it works: they move with the text as
it is edited, so filling in a long value does not put every later stop in the
wrong place.

It ends the moment somebody leaves — a click elsewhere, Escape, or the last
stop. An editing mode you cannot get out of is worse than no editing mode.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import Gdk, Gtk

from backsight.engine.library.placeholders import Filled, resolve


class Stops:
    """One insertion being filled in, and where the caret goes next."""

    def __init__(self, view, on_finished: Callable[[], None] | None = None) -> None:
        self._view = view
        self._buffer = view.get_buffer()
        self._on_finished = on_finished
        self._marks: list[tuple[Gtk.TextMark, Gtk.TextMark, bool]] = []
        self._at = -1
        self._keys: Gtk.EventControllerKey | None = None

    @property
    def is_live(self) -> bool:
        return bool(self._marks)

    @property
    def remaining(self) -> int:
        return max(0, len(self._marks) - self._at - 1)

    def insert(self, body: str) -> Filled:
        """Puts the text in at the caret and takes the first stop.

        The indentation of the line it lands on is carried onto every line
        after the first — a block pasted at the wrong depth is the first thing
        anybody has to fix.

        Indented **before** the placeholders are resolved, so every offset the
        resolver reports is an offset into the text that was actually inserted.
        Doing it the other way round meant computing how far each stop had
        shifted, which is arithmetic with nothing checking it.
        """
        self.stop()
        buffer = self._buffer
        at = buffer.get_iter_at_mark(buffer.get_insert())
        filled = resolve(_indented(body, _indentation_at(at)))

        buffer.begin_user_action()
        start_offset = at.get_offset()
        buffer.insert(at, filled.text)
        buffer.end_user_action()

        for stop in filled.stops:
            first = buffer.get_iter_at_offset(start_offset + stop.start)
            last = buffer.get_iter_at_offset(start_offset + stop.end)
            self._marks.append(
                (
                    buffer.create_mark(None, first, True),
                    buffer.create_mark(None, last, False),
                    stop.is_the_end,
                )
            )
        if not self._marks:
            return filled
        self._watch()
        self._at = -1
        self.next()
        return filled

    def next(self) -> bool:
        """Moves to the stop after this one. False when there is not one."""
        if not self._marks:
            return False
        self._at += 1
        if self._at >= len(self._marks):
            self.stop()
            return False
        self._select(self._at)
        # The end marker is where the caret rests, so arriving there is the end.
        if self._marks[self._at][2]:
            self.stop()
        return True

    def previous(self) -> bool:
        if not self._marks or self._at <= 0:
            return False
        self._at -= 1
        self._select(self._at)
        return True

    def stop(self) -> None:
        """Ends it, leaving the text and the caret exactly where they are."""
        for first, last, _ in self._marks:
            self._buffer.delete_mark(first)
            self._buffer.delete_mark(last)
        self._marks = []
        self._at = -1
        if self._keys is not None:
            self._view.remove_controller(self._keys)
            self._keys = None
        if self._on_finished is not None:
            self._on_finished()

    def _select(self, index: int) -> None:
        first, last, _ = self._marks[index]
        buffer = self._buffer
        buffer.select_range(buffer.get_iter_at_mark(first), buffer.get_iter_at_mark(last))
        self._view.scroll_to_mark(first, 0.1, False, 0.0, 0.5)

    def _watch(self) -> None:
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._pressed)
        self._view.add_controller(keys)
        self._keys = keys

    def _pressed(self, _controller, keyval: int, _code: int, state) -> bool:
        if not self._marks:
            return False
        if keyval == Gdk.KEY_Escape:
            self.stop()
            return True
        if keyval == Gdk.KEY_Tab and not (state & Gdk.ModifierType.SHIFT_MASK):
            self.next()
            return True
        if keyval in (Gdk.KEY_ISO_Left_Tab, Gdk.KEY_Tab) and state & Gdk.ModifierType.SHIFT_MASK:
            self.previous()
            return True
        return False


def _indentation_at(where) -> str:
    """The whitespace the line under the caret starts with."""
    line = where.copy()
    line.set_line_offset(0)
    end = line.copy()
    end.forward_to_line_end()
    text = line.get_text(end)
    return text[: len(text) - len(text.lstrip())]


def _indented(text: str, prefix: str) -> str:
    """Every line after the first, at the depth the first one landed at."""
    if not prefix:
        return text
    lines = text.split("\n")
    return "\n".join(
        [lines[0]] + [f"{prefix}{line}" if line.strip() else line for line in lines[1:]]
    )
