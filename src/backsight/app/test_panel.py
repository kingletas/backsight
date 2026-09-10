"""The test tree, and what a failing assertion actually evaluated to.

The tree is built from `test_abstract` before anything has run, so the
shape appears at once rather than filling in from empty.

The failure detail is the point of the whole feature: **both sides of the
comparison, plus the underlying value**, because "assertion failed" with no
values is why people stop writing these. The engine's JSON carries it; this
shows it.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.app import empty_state
from backsight.engine.tests.execution import DEFAULT_TARGET, Target
from backsight.engine.tests.results import Failure, Results, Run, Status, TestFile

# Shape as well as colour, so a run's state survives a monochrome screenshot.
MARKS = {
    Status.PASSED: "✓",
    Status.FAILED: "✗",
    Status.ERRORED: "!",
    Status.SKIPPED: "–",
    Status.PENDING: "·",
}

# A test result is a consequence too: a failure means the change is not safe
# to make, which is the same family as an irreversible one.
TONES = {
    Status.PASSED: "tf-safe",
    Status.FAILED: "tf-irreversible",
    Status.ERRORED: "tf-blocked",
    Status.SKIPPED: "tf-faint",
    Status.PENDING: "tf-faint",
}


class TestPanel(Adw.Bin):
    """Files, runs, and the detail of anything that failed."""

    def __init__(self, on_run: Callable[[Target], None] | None = None) -> None:
        super().__init__()
        self._on_run = on_run
        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._headline = Gtk.Label(xalign=0.0)
        self._headline.add_css_class("tf-medium")
        self._target = Gtk.Label(xalign=0.0, wrap=True)
        self._target.add_css_class("tf-small")
        self._target.add_css_class("tf-faint")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for margin in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{margin}")(12 if margin in ("start", "end") else 10)
        # An empty state that names an action and does not offer it is the
        # thing the stacks view was fixed for. This is that action.
        self.run = Gtk.Button(label="Run tests")
        self.run.set_halign(Gtk.Align.START)
        self.run.connect(
            "clicked", lambda *_: self._on_run(DEFAULT_TARGET) if self._on_run else None
        )

        box.append(self._headline)
        box.append(self._target)
        box.append(self.run)
        box.append(self._list)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_child(box)
        self.set_child(scroller)
        self.waiting()

    def waiting(self, why: str = "No tests have run") -> None:
        """Nothing has run, said centred and once — with the thing that would
        change it, because here there is one."""
        self._headline.set_visible(False)
        self._target.set_visible(False)
        self.run.set_visible(False)
        self._clear()
        self._list.append(
            empty_state.build(
                "No tests have run",
                why
                if why != "No tests have run"
                else "A `.tftest.hcl` file is what this runs. Nothing here has one yet.",
                glyph="✓",
                action="Run all tests",
                on_act=(lambda: self._on_run(DEFAULT_TARGET)) if self._on_run else None,
            )
        )

    def show(self, results: Results, target: Target = Target.MOCKS) -> None:
        self._headline.set_visible(True)
        self._target.set_visible(True)
        self.run.set_visible(True)
        self._headline.set_label(results.summary() or "No tests found")
        # The target is stated on every result. A green run against mocks and a
        # green run against a real account are not the same claim.
        self._target.set_label(f"Ran against {target.value}. {target.description}")
        self._clear()
        for file in results.files:
            self._list.append(_file_row(file))
            for run in file.runs:
                self._list.append(_run_row(run))
                for failure in run.failures:
                    self._list.append(_failure_row(failure))

    def _clear(self) -> None:
        while (child := self._list.get_first_child()) is not None:
            self._list.remove(child)


def _marked(text: str, status: Status, *, indent: int = 0) -> Gtk.Widget:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.set_margin_start(indent)
    mark = Gtk.Label(label=MARKS[status])
    mark.add_css_class("tf-mark")
    mark.add_css_class(TONES[status])
    row.append(mark)
    label = Gtk.Label(label=text, xalign=0.0, wrap=True)
    row.append(label)
    return row


def _file_row(file: TestFile) -> Gtk.Widget:
    return _marked(file.path, file.status)


def _run_row(run: Run) -> Gtk.Widget:
    return _marked(run.name, run.status, indent=16)


def _failure_row(failure: Failure) -> Gtk.Widget:
    """The condition, then what each expression in it turned out to be."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.set_margin_start(34)
    box.set_margin_bottom(6)

    condition = Gtk.Label(label=failure.condition, xalign=0.0, wrap=True, selectable=True)
    condition.add_css_class("tf-mono")
    condition.add_css_class("tf-small")
    box.append(condition)

    for value in failure.values:
        # The line that decides whether somebody keeps writing these.
        shown = Gtk.Label(label=str(value), xalign=0.0, wrap=True, selectable=True)
        shown.add_css_class("tf-mono")
        shown.add_css_class("tf-small")
        shown.add_css_class("tf-irreversible")
        box.append(shown)

    if failure.detail:
        message = Gtk.Label(label=failure.detail, xalign=0.0, wrap=True)
        message.add_css_class("tf-small")
        message.add_css_class("tf-faint")
        box.append(message)

    if not failure.has_evidence:
        # Said out loud rather than left as an empty space, so nobody wonders
        # whether the values were hidden or simply absent.
        none = Gtk.Label(label="The engine reported no values for this condition.", xalign=0.0)
        none.add_css_class("tf-small")
        none.add_css_class("tf-faint")
        box.append(none)

    where = Gtk.Label(label=f"{failure.path}:{failure.line}", xalign=0.0)
    where.add_css_class("tf-small")
    where.add_css_class("tf-faint")
    box.append(where)
    return box
