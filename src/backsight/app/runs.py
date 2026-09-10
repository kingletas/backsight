"""Getting a run's output onto the main loop, which is the only safe place for it.

The engine's runner calls back from a worker thread. Touching a widget from that
thread is undefined behaviour that usually looks like it works. Everything the
window hears from a run comes through here.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib

from backsight.engine.runner import process
from backsight.engine.runner.process import Result, Run


def start(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float | None = None,
    on_line: Callable[[str], None] | None = None,
    on_done: Callable[[Result], None] | None = None,
) -> Run:
    """Starts a run whose callbacks arrive on the main loop."""

    def line(text: str) -> None:
        if on_line is not None:
            GLib.idle_add(on_line, text, priority=GLib.PRIORITY_DEFAULT_IDLE)

    def done(result: Result) -> None:
        if on_done is not None:
            GLib.idle_add(on_done, result, priority=GLib.PRIORITY_DEFAULT_IDLE)

    return process.start(command, cwd=cwd, timeout=timeout, on_line=line, on_done=done)


def on_main_loop(callback: Callable[..., None]) -> Callable[..., None]:
    """Wraps a callback so it runs on the main loop instead of a worker thread.

    Touching a widget from a worker thread is undefined behaviour that usually
    looks like it works, which is the worst way for it to be wrong.
    """

    def hand_over(*arguments: object, **named: object) -> None:
        GLib.idle_add(lambda: (callback(*arguments, **named), False)[1])

    return hand_over
