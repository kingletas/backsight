"""The gutter: one glyph per line, and one bar down each block the plan touches.

When everything else is off — rail, drawer, change map, the lane — **the gutter
survives.** It is the cheapest thing on the screen and the most load-bearing,
and a mark saying a database is about to be replaced is the product.

Two channels, and they answer two different questions.

**The mark** says *there is something on this line*: one glyph, highest
consequence wins, and it differs by **shape** as well as colour, so it survives
a monochrome screenshot, a red-green reader, and a bug report pasted into a
ticket.

**The spine** says *the plan will do something to this block*: one continuous
three-pixel bar down the whole block with rounded caps, rather than the same
glyph repeated on every line of it. A resource then reads as a bracketed region
and the shape of a change is legible before a word of it is. An **exposure has
no spine** — it is a property of what the block already is, not something the
plan is about to do to it.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gsk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import Gdk, Graphene, Gsk, Gtk, GtkSource

from backsight.app.theme import tokens
from backsight.engine.insight.verdicts import Verdict

# Shape first, in priority order. Each is one character wide so the gutter
# costs the same whatever is in it.
SHAPES = {
    "blocked": "■",
    "destroy": "▼",
    "replace": "▲",
    "exposure": "●",
    "change": "◆",
    "add": "＋",
    "hint": "▸",
    # A data source being read. It changes nothing, so it is the quietest mark
    # here — but it is still a mark, because it is something the plan will do.
    "none": "▸",
}

# Which mark wins when two land on one line. The order above, as numbers.
PRIORITY = {tone: len(SHAPES) - at for at, tone in enumerate(SHAPES)}

# What colour each tone draws in. Replace keeps its own because it is neither a
# create nor a destroy, and it is the change people misread most.
TONES = {
    "blocked": "blocked_edge",
    "destroy": "plan_destroy",
    "replace": "plan_replace",
    "exposure": "consequence_irreversible_edge",
    "change": "plan_update",
    "add": "plan_create",
    "hint": "ink_faint",
    "none": "plan_noop",
}

# The spine says the plan will act here. An exposure and a finding do not.
NO_SPINE = ("exposure", "blocked", "hint", "none")

WIDTH = tokens.GUTTER["mark"]
SPINE_WIDTH = tokens.GUTTER["spine"]


class Marks(GtkSource.GutterRendererText):
    """One mark per line, from whatever verdicts the plan produced.

    **A mark is a thing you can point at.** It carries the finding, so a click
    opens the explanation and a right-click opens the menu that is about it —
    the mouse inventory has said so since it was written, and neither worked:
    the renderer had no gesture on it at all.
    """

    def __init__(
        self,
        on_activate: Callable[[int], None] | None = None,
        on_menu: Callable[[int, float, float], None] | None = None,
    ) -> None:
        super().__init__()
        self.set_size_request(WIDTH, -1)
        self.set_xpad(2)
        self._by_line: dict[int, Verdict] = {}
        self._on_activate = on_activate
        self._on_menu = on_menu
        # query-data carries the line number; GutterLines is the batch.
        self.connect("query-data", self._on_query)

        click = Gtk.GestureClick()
        click.connect("released", self._clicked)
        self.add_controller(click)
        menu = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        menu.connect("pressed", self._asked)
        self.add_controller(menu)

    def _line_at(self, y: float) -> int | None:
        """Which line a point in the gutter is on, or nothing when it is on one
        with no mark — pointing at blank gutter is not pointing at a finding."""
        view = self.get_view()
        if view is None:
            return None
        _x, buffer_y = view.window_to_buffer_coords(Gtk.TextWindowType.LEFT, 0, int(y))
        found, _top = view.get_line_at_y(buffer_y)
        line = found.get_line()
        return line if line in self._by_line else None

    def _clicked(self, _gesture, _presses: int, _x: float, y: float) -> None:
        line = self._line_at(y)
        if line is not None and self._on_activate is not None:
            self._on_activate(line)

    def _asked(self, _gesture, _presses: int, x: float, y: float) -> None:
        line = self._line_at(y)
        if line is not None and self._on_menu is not None:
            self._on_menu(line, x, y)

    def show(self, verdicts: list[Verdict]) -> None:
        """Replaces the marks. One per line; the most consequential wins."""
        found: dict[int, Verdict] = {}
        for verdict in verdicts:
            line = verdict.line - 1
            existing = found.get(line)
            if existing is None or _weight(verdict) > _weight(existing):
                found[line] = verdict
        self._by_line = found
        self.queue_draw()

    def clear(self) -> None:
        self._by_line = {}
        self.queue_draw()

    def verdict_at(self, line: int) -> Verdict | None:
        """What the mark on this line is about, for a click or a hover."""
        return self._by_line.get(line)

    def _on_query(self, _renderer, _lines, line: int) -> None:
        verdict = self._by_line.get(line)
        if verdict is None:
            self.set_text("", -1)
            self.set_tooltip_text("")
            return
        self.set_text(SHAPES.get(verdict.tone, "▸"), -1)
        self.set_tooltip_text(verdict.text)


class Spine(GtkSource.GutterRenderer):
    """One bar per block the plan touches, drawn as a region rather than a row.

    Only the caps are rounded, so consecutive lines of one block join into a
    single bar and two adjacent blocks still read as two.
    """

    def __init__(self) -> None:
        super().__init__()
        self.set_size_request(SPINE_WIDTH + 4, -1)
        self._tone: dict[int, str] = {}
        self._first: set[int] = set()
        self._last: set[int] = set()

    def show(self, verdicts: list[Verdict]) -> None:
        """Replaces the spines with the blocks these verdicts are about."""
        tone: dict[int, str] = {}
        first: set[int] = set()
        last: set[int] = set()
        for verdict in verdicts:
            if verdict.tone in NO_SPINE:
                continue
            block = verdict.block
            for line in block:
                at = line - 1
                if at not in tone or PRIORITY.get(verdict.tone, 0) > PRIORITY.get(tone[at], 0):
                    tone[at] = verdict.tone
            first.add(block.start - 1)
            last.add(block.stop - 2)
        self._tone, self._first, self._last = tone, first, last
        self.queue_draw()

    def clear(self) -> None:
        self._tone, self._first, self._last = {}, set(), set()
        self.queue_draw()

    def do_snapshot_line(self, snapshot, lines, line: int) -> None:
        tone = self._tone.get(line)
        if tone is None:
            return
        y, height = lines.get_line_yrange(line, GtkSource.GutterRendererAlignmentMode.CELL)
        colour = tokens.color(TONES.get(tone, "plan_noop"))
        # A cap on the ends of the block and a square join everywhere else, so
        # a five-line resource is one bar and not five.
        cap = SPINE_WIDTH / 2
        radius = Graphene.Size()
        radius.init(cap, cap)
        none = Graphene.Size()
        none.init(0, 0)
        area = Graphene.Rect()
        area.init(1, y, SPINE_WIDTH, height)
        rounded = Gsk.RoundedRect()
        rounded.init(
            area,
            radius if line in self._first else none,
            radius if line in self._first else none,
            radius if line in self._last else none,
            radius if line in self._last else none,
        )
        snapshot.push_rounded_clip(rounded)
        snapshot.append_color(colour, area)
        snapshot.pop()


def _weight(verdict: Verdict) -> int:
    """A destroy on the same line as an add shows the destroy."""
    return PRIORITY.get(verdict.tone, 0)


def install(
    view: GtkSource.View,
    *,
    on_activate: Callable[[int], None] | None = None,
    on_menu: Callable[[int, float, float], None] | None = None,
) -> tuple[Marks, Spine]:
    """The spine, then the mark, in the order the design reads them."""
    gutter = view.get_gutter(Gtk.TextWindowType.LEFT)
    spine = Spine()
    marks = Marks(on_activate=on_activate, on_menu=on_menu)
    # Sort positions, not indices: the line-number renderer GtkSourceView adds
    # for itself sits at zero, and the design's order is fold, number, spine,
    # mark. Leaving gaps means a fifth renderer can be put between two of these
    # without renumbering the rest.
    gutter.insert(spine, 10)
    gutter.insert(marks, 20)
    return marks, spine


def colour_of(tone: str) -> Gdk.RGBA:
    """One tone as an RGBA, for anything drawing rather than styling."""
    return tokens.color(TONES.get(tone, "plan_noop"))
