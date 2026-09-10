"""Every other place the selected word appears, outlined rather than filled.

Sublime's cheapest good idea: select a word and you can see the rest of them
without searching. It costs nothing and it answers the question people open a
search bar for.

**Outline, never fill.** A fill stacks with the spine, the current-line wash
and the plan wash, and three translucent layers on one row turn a screen of
code to mud. GTK's text tags have no border, so the outline is a one-pixel rule
above and below in the accent — thin, uncoloured in the middle, and legible
against every wash there is.

The selection itself is left alone. Marking the thing under the caret as well
as its siblings makes it hard to tell which one you are on.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import GLib, Gtk, GtkSource, Pango

from backsight.app.theme import tokens

TAG = "backsight-occurrence"

# Below this a selection is a fragment rather than a word, and outlining every
# `id` in a file is noise.
SHORTEST = 3

# Above this the selection is a passage, and what somebody wants from it is not
# a survey of where else it appears.
LONGEST = 120

# More than this and the screen is striped. A word that common is not being
# looked for.
MOST = 200


def is_a_word(said: str) -> bool:
    """Whether a selection is the kind of thing worth outlining elsewhere."""
    stripped = said.strip()
    return (
        SHORTEST <= len(stripped) <= LONGEST
        and stripped == said
        and not any(character.isspace() for character in said)
    )


def places(text: str, word: str, *, limit: int = MOST) -> list[tuple[int, int]]:
    """Every whole-word occurrence, as (start, end) offsets into the text."""
    if not is_a_word(word):
        return []
    found: list[tuple[int, int]] = []
    at = text.find(word)
    while at != -1 and len(found) < limit:
        before = text[at - 1] if at else ""
        after = text[at + len(word) : at + len(word) + 1]
        if not _joins(before) and not _joins(after):
            found.append((at, at + len(word)))
        at = text.find(word, at + 1)
    return found


def _joins(character: str) -> bool:
    """Whether a character would make this occurrence part of a longer word."""
    return bool(character) and (character.isalnum() or character in "_-")


class Occurrences:
    """Keeps the outlines in step with what is selected in one buffer."""

    def __init__(self, view: GtkSource.View) -> None:
        self._view = view
        self._buffer = view.get_buffer()
        self._pending: int | None = None
        self._buffer.connect("notify::has-selection", lambda *_: self._schedule())
        self._buffer.connect("mark-set", self._on_mark)
        self._buffer.connect("changed", lambda *_: self._schedule())

    def _on_mark(self, _buffer, _where, mark) -> None:
        if mark.get_name() in ("insert", "selection_bound"):
            self._schedule()

    def _schedule(self) -> None:
        # Coalesced: dragging a selection emits mark-set per character, and
        # rescanning the file on each one is the one way this becomes expensive.
        if self._pending is not None:
            return
        self._pending = GLib.idle_add(self._apply, priority=GLib.PRIORITY_DEFAULT_IDLE)

    def _tag(self):
        table = self._buffer.get_tag_table()
        found = table.lookup(TAG)
        if found is not None:
            return found
        colour = tokens.color("accent_edge")
        return self._buffer.create_tag(
            TAG,
            underline=Pango.Underline.SINGLE,
            underline_rgba=colour,
            overline=Pango.Overline.SINGLE,
            overline_rgba=colour,
        )

    def clear(self) -> None:
        tag = self._buffer.get_tag_table().lookup(TAG)
        if tag is not None:
            self._buffer.remove_tag(tag, self._buffer.get_start_iter(), self._buffer.get_end_iter())

    def _apply(self) -> bool:
        self._pending = None
        self.clear()
        bounds = self._buffer.get_selection_bounds()
        if not bounds:
            return False
        start, end = bounds
        word = self._buffer.get_text(start, end, False)
        text = self._buffer.get_text(
            self._buffer.get_start_iter(), self._buffer.get_end_iter(), False
        )
        chosen = (start.get_offset(), end.get_offset())
        tag = self._tag()
        for at, to in places(text, word):
            if (at, to) == chosen:
                # The one you are on is already marked, by being selected.
                continue
            self._buffer.apply_tag(
                tag, self._buffer.get_iter_at_offset(at), self._buffer.get_iter_at_offset(to)
            )
        return False


class Reserved(GtkSource.GutterRendererText):
    """A column that is always there and never draws anything.

    Folding has no API in GtkSourceView 5. The twelve pixels it would need are
    held anyway, so the day it becomes possible nothing reflows — and so the
    gutter is the same width whether a plan has run or not, which is what stops
    the code sliding sideways under a reader when one finishes.
    """

    def __init__(self, width: int) -> None:
        super().__init__()
        self.set_size_request(width, -1)
        self.connect("query-data", lambda *_a: self.set_text("", -1))


def install(view: GtkSource.View) -> Occurrences:
    """Reserves the fold column and starts outlining occurrences."""
    view.get_gutter(Gtk.TextWindowType.LEFT).insert(Reserved(tokens.GUTTER["fold"]), -10)
    return Occurrences(view)
