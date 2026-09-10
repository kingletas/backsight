"""A mark beside each `run` block saying how it last went.

The shapes are the test panel's, so the gutter and the panel say the
same thing the same way.

Clicking a mark runs the **file**, not the run beside the cursor: the engine's
only filter is file-level, and a control that quietly does more than its label
says is the defect this product exists to prevent. See
`docs/findings/005-a-single-run-cannot-be-re-run.md`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import Gtk, GtkSource

from backsight.app.test_panel import MARKS
from backsight.engine.tests.locations import RunBlock, runs
from backsight.engine.tests.results import Results, Status, TestFile


@dataclass(frozen=True)
class Mark:
    """One run block, and how it last went."""

    block: RunBlock
    status: Status

    @property
    def shape(self) -> str:
        return MARKS[self.status]

    def tooltip(self, path: Path | None, count: int) -> str:
        """Says what will happen, which is the file and not this run alone."""
        where = path.name if path is not None else "this file"
        runs_word = "run" if count == 1 else "runs"
        return (
            f"{self.block.name} — {self.status.value}\n"
            f"Click to run {where} again ({count} {runs_word})."
        )


class RunMarks(GtkSource.GutterRendererText):
    """One mark per run block, from the last results this file produced."""

    def __init__(self, on_activate: Callable[[Path], None] | None = None) -> None:
        super().__init__()
        self.set_size_request(16, -1)
        self.set_xpad(4)
        self._on_activate = on_activate
        self._by_line: dict[int, Mark] = {}
        self._path: Path | None = None
        self._count = 0
        self.connect("query-data", self._on_query)

        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)

    def show(self, source: bytes, results: Results | None, path: Path | None = None) -> None:
        """Marks every run block in the file, whether it has run or not.

        `path` is relative to the workspace, because that is how the engine
        names a file in its results. A run with no result is `PENDING` rather
        than absent, so the shape of the file appears before anything has run.
        """
        self._path = path
        reported = _file_in(results, path)
        found: dict[int, Mark] = {}
        blocks = runs(source)
        for block in blocks:
            result = reported.run(block.name) if reported is not None else None
            status = result.status if result is not None else Status.PENDING
            found[block.line - 1] = Mark(block=block, status=status)
        self._by_line = found
        self._count = len(blocks)
        self.queue_draw()

    def clear(self) -> None:
        self._by_line = {}
        self._count = 0
        self.queue_draw()

    def mark_at(self, line: int) -> Mark | None:
        return self._by_line.get(line)

    def _on_query(self, _renderer, _lines, line: int) -> None:
        mark = self._by_line.get(line)
        if mark is None:
            self.set_text("", -1)
            self.set_tooltip_text("")
            return
        self.set_text(mark.shape, -1)
        self.set_tooltip_text(mark.tooltip(self._path, self._count))

    def _on_click(self, _gesture, _presses: int, _x: float, y: float) -> None:
        if self._on_activate is None or self._path is None:
            return
        view = self.get_view()
        if view is None:
            return
        _, buffer_y = view.window_to_buffer_coords(Gtk.TextWindowType.LEFT, 0, int(y))
        found, _ = view.get_line_at_y(buffer_y)
        if self._by_line.get(found.get_line()) is None:
            return
        self._on_activate(self._path)


def install(view: GtkSource.View, on_activate=None) -> RunMarks:
    marks = RunMarks(on_activate=on_activate)
    view.get_gutter(Gtk.TextWindowType.LEFT).insert(marks, 0)
    return marks


def _file_in(results: Results | None, path: Path | None) -> TestFile | None:
    """The results for one file, matched the way the engine names it.

    The engine keys results on the path it was given, relative to the
    workspace. Falling back to the basename covers a file reported under a
    path we spelled differently; two test files with the same basename in
    different directories would collide, so the exact key is tried first.
    """
    if results is None or path is None:
        return None
    exact = results.file(str(path))
    if exact is not None:
        return exact
    for candidate in results.files:
        if Path(candidate.path).name == path.name:
            return candidate
    return None
