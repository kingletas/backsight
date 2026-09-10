"""A strip beside the file showing where the plan touches it, by action.

Not a minimap: a thumbnail of text you are already looking at tells you nothing
you cannot see. **Where the plan changes things** is a fact about the whole file
that is otherwise invisible until you scroll to it.

Four things make it a map rather than a decoration, and the version this
replaces had none of them: it is fourteen pixels wide instead of eight, a mark
is a solid bar proportional to the block rather than a two-pixel tick, findings
sit as pips on the left edge so they never compete with the plan, and a
translucent rectangle says which part of the file you are looking at.

It is drawn rather than rendered from text, so a 5,000-line file costs the same
as a 50-line one — a mark is a rectangle, and there are as many rectangles as
there are changes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gtk

from backsight.app.theme import tokens

WIDTH = tokens.MAP_WIDTH

# The shortest a mark may be. One line in a 4,000-line file is a fraction of a
# pixel, and a mark you cannot see is not a mark.
MINIMUM = 3.0

# Findings ride the left edge in their own narrow column, so a file with a
# policy finding on every other line still reads as a plan first.
PIP = 3.0

# Drawn last wins, so the most consequential is drawn last.
ORDER = ("none", "hint", "add", "change", "replace", "destroy", "exposure", "blocked")

# What a finding is, as opposed to something the plan will do. These take the
# pip column; everything else takes the bar.
FINDINGS = ("exposure", "hint", "blocked")


@dataclass(frozen=True)
class Mark:
    """One change, at one line, over as many lines as the block covers."""

    line: int
    tone: str
    last_line: int = 0

    @property
    def height(self) -> int:
        """How many lines this mark covers. At least one."""
        return max(1, self.last_line - self.line + 1)


class ChangeMap(Gtk.DrawingArea):
    """The strip. Click to scroll there; drag the viewport; hover says what is there."""

    def __init__(self, on_go_to: Callable[[int], None] | None = None) -> None:
        super().__init__()
        self._marks: list[Mark] = []
        self._lines = 1
        self._colours: dict[str, Gdk.RGBA] = {}
        self._on_go_to = on_go_to
        # Which lines are on screen, so the strip says where you are in the
        # file as well as what is in it. Zero means nobody has said yet.
        self._viewport: tuple[int, int] = (0, 0)
        self.add_css_class("tf-change-map")
        self.set_size_request(WIDTH, -1)
        self.set_draw_func(self._draw)

        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)
        drag = Gtk.GestureDrag()
        drag.connect("drag-update", self._on_drag)
        self.add_controller(drag)
        self.set_has_tooltip(True)
        self.connect("query-tooltip", self._on_tooltip)

    def show(self, marks: list[Mark], lines: int) -> None:
        """Replaces the marks. `lines` is how long the file is."""
        self._marks = sorted(
            marks, key=lambda mark: ORDER.index(mark.tone) if mark.tone in ORDER else 0
        )
        self._lines = max(1, lines)
        self.queue_draw()

    def clear(self) -> None:
        self._marks = []
        self.queue_draw()

    def looking_at(self, first: int, last: int) -> None:
        """Which lines are on screen right now."""
        if (first, last) == self._viewport:
            return
        self._viewport = (first, last)
        self.queue_draw()

    def use_colours(self, colours: dict[str, Gdk.RGBA]) -> None:
        """The tones, resolved once by whoever owns the theme."""
        self._colours = dict(colours)
        self.queue_draw()

    def line_at(self, y: float) -> int:
        """Which line a point on the strip is. 1-based, as a person counts."""
        height = self.get_height() or 1
        return max(1, min(self._lines, int(y / height * self._lines) + 1))

    def mark_near(self, y: float, within: int = 0) -> Mark | None:
        """The mark closest to a point, if one is close enough to have been meant.

        `within` defaults to a share of the file rather than a number of lines,
        so the tolerance is the same distance on screen in a long file and a
        short one.
        """
        if not self._marks:
            return None
        line = self.line_at(y)
        allowed = within or max(1, self._lines // 40)
        inside = [mark for mark in self._marks if mark.line <= line <= mark.line + mark.height]
        if inside:
            return max(inside, key=lambda mark: ORDER.index(mark.tone))
        closest = min(self._marks, key=lambda mark: abs(mark.line - line))
        return closest if abs(closest.line - line) <= allowed else None

    def _draw(self, _area, context, width: int, height: int) -> None:
        scale = height / self._lines
        for mark in self._marks:
            colour = self._colours.get(mark.tone)
            if colour is None:
                continue
            top = (mark.line - 1) * scale
            context.set_source_rgba(colour.red, colour.green, colour.blue, colour.alpha)
            if mark.tone in FINDINGS:
                # The left edge, and never more than a pip. A finding is a
                # different question from what the plan will do, so it gets a
                # different channel rather than a louder version of the same one.
                context.rectangle(0, top, PIP, MINIMUM)
            else:
                context.rectangle(PIP + 1, top, width - PIP - 1, max(MINIMUM, mark.height * scale))
            context.fill()

        first, last = self._viewport
        if last <= first:
            return
        viewport = tokens.color("map_viewport")
        context.set_source_rgba(viewport.red, viewport.green, viewport.blue, viewport.alpha)
        top = (first - 1) * scale
        context.rectangle(0, top, width, max(MINIMUM, (last - first + 1) * scale))
        context.fill()

    def _on_click(self, _gesture, _presses: int, _x: float, y: float) -> None:
        if self._on_go_to is not None:
            self._on_go_to(self.line_at(y))

    def _on_drag(self, gesture, _dx: float, dy: float) -> None:
        """Dragging the strip scrolls the file, the way dragging a scrollbar does."""
        found, start = gesture.get_start_point()
        if found and self._on_go_to is not None:
            self._on_go_to(self.line_at(start + dy))

    def _on_tooltip(self, _widget, _x: int, y: int, _keyboard: bool, tooltip) -> bool:
        """Hover says what a mark means without navigating away from where you are."""
        mark = self.mark_near(y)
        if mark is None:
            return False
        last = mark.line + mark.height - 1
        span = f"Lines {mark.line}–{last}" if mark.height > 1 else f"Line {mark.line}"
        tooltip.set_text(f"{span} — {mark.tone}")
        return True
