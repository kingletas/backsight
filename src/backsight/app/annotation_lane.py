"""The lane: an annotation at the right of the line it is about, on its own row.

**Nothing that annotates code may displace code.** Line *n* is at *n* times the
row height, always, so the numbers are a ruler you can count on, paging moves a
predictable distance, and the change map beside the buffer maps onto what is in
front of you.

The rows this replaces reserved 26 pixels under a line and floated a widget
into the gap. It read well and it cost the grid: with a plan open, line 12 was
no longer the twelfth row, and the leading had been opened to 1.85 to make the
interstitials breathe — a quarter of every screen of code, spent on commentary.

A lane annotation is sans, right-aligned, quiet, truncated at one line and
capped at a share of the width. **When the code reaches it, the code wins and
the lane disappears**; the gutter mark and the hover still carry the finding.
"""

from __future__ import annotations

from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import GLib, Gtk, GtkSource, Pango

from backsight.app.theme import tokens
from backsight.engine.insight.verdicts import Verdict

# The share of the buffer the lane may take. Past this a long annotation is
# competing with the code rather than commenting on it.
SHARE = 0.46

# The narrowest lane worth drawing. Below it an annotation is an ellipsis.
MINIMUM = 90

# Between the last character of code and the first of the annotation. Less than
# this and the two read as one string.
GAP = 24

# The scroller draws its bar as an overlay across the right edge of the view,
# so the last characters of a right-aligned lane were under it. Measured
# against a stock Adwaita scrollbar, and one pixel of clearance on top.
SCROLLBAR = 15


@dataclass(frozen=True)
class Annotation:
    """One thing to say about one line.

    `kind` decides when it is drawn, which is the rule that keeps a screenful
    readable — see `visible_on`.
    """

    line: int
    text: str
    tone: str
    kind: str = "explanation"

    @classmethod
    def of(cls, verdict: Verdict) -> Annotation:
        return cls(line=verdict.line, text=verdict.text, tone=verdict.tone)


# How consequential each tone is. Two annotations on one line become one, and
# the more consequential tone decides how it looks — the same rule the gutter
# uses for two marks on one line.
WEIGHT = {"blocked": 5, "destroy": 4, "replace": 3, "exposure": 2, "change": 1, "add": 1, "hint": 0}

# Which consequence each plan action carries. Four levels, and the annotation
# never invents a fifth.
LEVELS = {
    "add": "tf-safe",
    "change": "tf-disruptive",
    "replace": "tf-irreversible",
    "destroy": "tf-irreversible",
    "exposure": "tf-blocked",
    "blocked": "tf-blocked",
    "none": "tf-faint",
    "hint": "tf-faint",
}

# The wash behind the changed line itself. Row background only, so the syntax
# colours stay intact and the code is still readable inside it.
WASH_TOKENS = {
    "add": "consequence_safe_bg",
    "change": "consequence_disruptive_bg",
    "replace": "consequence_irreversible_bg",
    "destroy": "consequence_irreversible_bg",
    "exposure": "blocked_bg",
}

JOIN = " · "

TAG = "backsight-verdict-space"


def merge(annotations: list[Annotation]) -> list[Annotation]:
    """One annotation per line.

    Two on the same line were drawn on top of each other, which read as a
    single garbled string — a verdict and a code lens both belong to the line a
    resource starts on.
    """
    by_line: dict[int, list[Annotation]] = {}
    for annotation in annotations:
        by_line.setdefault(annotation.line, []).append(annotation)

    merged: list[Annotation] = []
    for line in sorted(by_line):
        found = by_line[line]
        if len(found) == 1:
            merged.append(found[0])
            continue
        loudest = max(found, key=lambda item: WEIGHT.get(item.tone, 0))
        merged.append(
            Annotation(
                line=line,
                text=JOIN.join(item.text for item in found),
                tone=loudest.tone,
                kind=min(found, key=lambda item: _ORDER.index(item.kind)).kind,
            )
        )
    return merged


# Drawn in this order of insistence, so a merged annotation keeps the rule of
# whichever half is shown most often.
_ORDER = ("lens", "explanation", "hint")


def visible_on(
    annotations: list[Annotation], *, first: int, last: int, caret: int | None
) -> list[Annotation]:
    """Which annotations may be drawn on the screenful between two lines.

    **One permanent explanation per screenful, and it is the worst one.** A wall
    of them is unreadable, and what people do about an unreadable wall is read
    none of it. Everything else stays a gutter mark until you go to the line.

    A lens is not an explanation — it is a fact about the block under it and it
    was asked for by a setting — so every lens in view is drawn. A resolved
    value is the opposite: it is only ever on the line the caret is on.
    """
    on_screen = [item for item in annotations if first <= item.line <= last]
    kept = [item for item in on_screen if item.kind == "lens"]
    here = [item for item in on_screen if item.line == caret and item.kind != "lens"]
    kept += here
    explanations = [item for item in on_screen if item.kind == "explanation" and item.line != caret]
    if explanations:
        kept.append(max(explanations, key=lambda item: WEIGHT.get(item.tone, 0)))
    return sorted(kept, key=lambda item: item.line)


class Lane:
    """Every lane annotation on one open file."""

    def __init__(self, view: GtkSource.View) -> None:
        self._view = view
        self._buffer = view.get_buffer()
        self._all: list[Annotation] = []
        self._placed: list[tuple[Gtk.Widget, int]] = []
        self._pool: list[Gtk.Widget] = []
        self._buffer.connect("changed", lambda *_: self._schedule())
        self._buffer.connect("notify::cursor-position", lambda *_: self._schedule())
        # A scroll changes which screenful is in view, and the worst
        # explanation on it. A resize changes where the lane starts.
        view.connect("notify::width-request", lambda *_: self._schedule())
        for adjustment in (view.get_vadjustment(), view.get_hadjustment()):
            if adjustment is not None:
                adjustment.connect("value-changed", lambda *_: self._schedule())

    def show(self, annotations: list[Verdict | Annotation]) -> None:
        """Replaces whatever was shown with these."""
        self._untag()
        said = [
            item if isinstance(item, Annotation) else Annotation.of(item) for item in annotations
        ]
        self._all = merge(said)
        for annotation in self._all:
            wash = self._wash(annotation.tone)
            if wash is None:
                continue
            found, start = self._buffer.get_iter_at_line(annotation.line - 1)
            if not found:
                # The file changed since the plan ran and the line is gone.
                # Washing anywhere else would be a guess.
                continue
            _reached, end = self._buffer.get_iter_at_line(annotation.line)
            self._buffer.apply_tag(wash, start, end)
        self._schedule()

    def clear(self) -> None:
        self._all = []
        for row in self._pool:
            row.set_visible(False)
        self._placed = []
        self._untag()

    def _row(self, index: int, annotation: Annotation) -> Gtk.Widget:
        """Reused rather than rebuilt.

        A `Gtk.TextView` will not give up an overlay child: `remove` says it is
        not a child, and `unparent` leaves the view trying to snapshot a widget
        it no longer owns. Hiding is the only thing that works, and it is
        cheaper than building a widget per plan.
        """
        while len(self._pool) <= index:
            made = Gtk.Label(xalign=1.0, ellipsize=Pango.EllipsizeMode.END, single_line_mode=True)
            made.add_css_class("tf-lane")
            self._view.add_overlay(made, 0, 0)
            self._pool.append(made)
        row = self._pool[index]
        for old in list(row.get_css_classes()):
            if old.startswith("tf-") and old != "tf-lane":
                row.remove_css_class(old)
        row.add_css_class(LEVELS.get(annotation.tone, "tf-faint"))
        row.set_label(annotation.text)
        row.set_tooltip_text(annotation.text)
        row.set_visible(True)
        return row

    def _wash(self, tone: str):
        """The tag that colours the changed line, from the theme's own palette.

        A text tag cannot take a CSS class, so the colour is read rather than
        styled — which is why the four names live in `components.css` as well,
        so nothing has to go looking for them.
        """
        token = WASH_TOKENS.get(tone)
        if token is None:
            return None
        name = f"{TAG}-{tone}"
        table = self._buffer.get_tag_table()
        found = table.lookup(name)
        if found is not None:
            return found
        return self._buffer.create_tag(name, background_rgba=tokens.color(token))

    def _untag(self) -> None:
        table = self._buffer.get_tag_table()
        whole = (self._buffer.get_start_iter(), self._buffer.get_end_iter())
        for name in (TAG, *(f"{TAG}-{tone}" for tone in WASH_TOKENS)):
            tag = table.lookup(name)
            if tag is not None:
                self._buffer.remove_tag(tag, *whole)

    def _schedule(self) -> None:
        """Places the annotations once the view has laid itself out again.

        `get_line_yrange` is stale until a layout pass has run, and a lane
        placed off a stale answer lands on the wrong line of somebody's file.
        """
        GLib.idle_add(self._place, priority=GLib.PRIORITY_HIGH_IDLE + 10)

    def _screenful(self) -> tuple[int, int]:
        """The first and last line currently in view, 1-based."""
        seen = self._view.get_visible_rect()
        top = self._view.get_iter_at_location(0, seen.y)
        bottom = self._view.get_iter_at_location(0, seen.y + seen.height)
        first = top[1].get_line() + 1 if top[0] else 1
        last = bottom[1].get_line() + 1 if bottom[0] else self._buffer.get_line_count()
        return first, max(first, last)

    def _caret(self) -> int:
        return self._buffer.get_iter_at_mark(self._buffer.get_insert()).get_line() + 1

    def _place(self) -> bool:
        """Puts each annotation at the right of the row its line already has."""
        seen = self._view.get_visible_rect()
        width = int(seen.width * SHARE)
        first, last = self._screenful()
        wanted = visible_on(self._all, first=first, last=last, caret=self._caret())

        drawn = 0
        for annotation in wanted:
            found, where = self._buffer.get_iter_at_line(annotation.line - 1)
            if not found:
                continue
            top, height = self._view.get_line_yrange(where)
            room = self._room_beside(annotation.line - 1, seen, width)
            if room < MINIMUM:
                # The code reached the lane. The code wins; the mark and the
                # hover still say there is something here.
                continue
            row = self._row(drawn, annotation)
            row.set_size_request(room, height)
            self._view.move_overlay(row, seen.x + seen.width - room - SCROLLBAR, top)
            drawn += 1

        for spare in self._pool[drawn:]:
            spare.set_visible(False)
        self._placed = self._placed[:drawn]
        return False

    def _room_beside(self, line: int, seen, wanted: int) -> int:
        """How much lane is left once the code on this line has had its width."""
        found, end = self._buffer.get_iter_at_line(line)
        if not found:
            return 0
        end.forward_to_line_end()
        where = self._view.get_iter_location(end)
        free = seen.x + seen.width - SCROLLBAR - (where.x + where.width) - GAP
        return min(wanted, max(0, int(free)))


def height_of_a_row() -> int:
    """What one row comes to, for anything that needs to reason about the grid."""
    return round(tokens.TYPE["code"] * tokens.LINE["code"])
