"""Planning while somebody types, without planning once per keystroke.

FR-ED-04. A save starts a clock rather than a plan; another save inside that
window restarts the clock. A save while a plan is already running cancels it,
because the answer it is working towards is about a file that no longer exists.

The rule that matters: **only the newest run may report.** An older plan
finishing after a newer one started would overwrite a current answer with a
stale one, and the person reading it has no way to tell.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from backsight.engine.plan.execution import PlanOutcome, speculative

# Long enough to survive a burst of saves, short enough to feel immediate.
DEBOUNCE_SECONDS = 0.6


class Stage(Enum):
    """What the speculator is doing, in the words the status line uses."""

    IDLE = "idle"
    WAITING = "waiting for you to stop typing"
    RUNNING = "planning"
    DONE = "planned"
    FAILED = "the plan failed"


@dataclass(frozen=True)
class Progress:
    """A stage change worth showing."""

    stage: Stage
    detail: str = ""


class Speculator:
    """Turns a stream of saves into at most one plan in flight."""

    def __init__(
        self,
        directory: Path,
        *,
        debounce: float = DEBOUNCE_SECONDS,
        on_progress: Callable[[Progress], None] | None = None,
        on_plan: Callable[[PlanOutcome], None] | None = None,
        plan: Callable[..., PlanOutcome] = speculative,
    ) -> None:
        self.directory = Path(directory)
        self._debounce = debounce
        self._on_progress = on_progress
        self._on_plan = on_plan
        self._plan = plan

        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._generation = 0
        self._running: threading.Thread | None = None
        self._cancel = threading.Event()
        # The engine process itself, while one is in flight. Cancelling used to
        # bump a generation counter and discard the answer; `tofu` kept running
        # and kept the state lock, so the next plan queued behind a run nobody
        # was waiting for and so did anybody else on the same workspace.
        self._process: object | None = None
        self.stage = Stage.IDLE

    def touched(self) -> None:
        """A file was saved. Starts or restarts the clock."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            # Anything in flight is now working on an old file.
            self._generation += 1
            self._cancel.set()
            self._timer = threading.Timer(self._debounce, self._begin)
            self._timer.daemon = True
            self._timer.start()
        self._report(Progress(Stage.WAITING))

    def now(self) -> None:
        """Somebody asked for a plan. There is nothing left to wait for.

        The clock exists to turn a burst of saves into one plan. A person who
        pressed Run plan has already stopped typing, so waiting out the debounce
        would be the application hesitating over a decision already made.
        """
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self._begin()

    def cancel(self) -> None:
        """Stops everything, and stops the engine rather than ignoring it."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._generation += 1
            self._cancel.set()
            running, self._process = self._process, None
        if running is not None:
            # Outside the lock: killing a process group waits on it, and
            # holding the lock through that would block the next save.
            running.cancel()
        self._report(Progress(Stage.IDLE))

    def wait(self, timeout: float = 60.0) -> None:
        """Blocks until nothing is pending. For tests, never for the interface."""
        timer = self._timer
        if timer is not None:
            timer.join(timeout)
        thread = self._running
        if thread is not None:
            thread.join(timeout)

    def _begin(self) -> None:
        with self._lock:
            self._generation += 1
            generation = self._generation
            self._cancel = threading.Event()
            cancel = self._cancel
        self._report(Progress(Stage.RUNNING))

        def remember(running: object) -> None:
            with self._lock:
                if generation == self._generation:
                    self._process = running

        def work() -> None:
            outcome = self._plan(self.directory, started=remember)
            with self._lock:
                if self._process is not None and generation == self._generation:
                    self._process = None
            with self._lock:
                superseded = generation != self._generation
            if superseded or cancel.is_set():
                # A newer save is already being answered. Reporting this one
                # would replace a current answer with an older one.
                return
            self.stage = Stage.DONE if outcome.ok else Stage.FAILED
            self._report(Progress(self.stage, outcome.failure or ""))
            if self._on_plan is not None:
                self._on_plan(outcome)

        thread = threading.Thread(target=work, name="backsight-speculate", daemon=True)
        self._running = thread
        thread.start()

    def _report(self, progress: Progress) -> None:
        self.stage = progress.stage
        if self._on_progress is not None:
            self._on_progress(progress)
