"""The one place a subprocess is started, so the window never waits on one.

NFR-04 says the interface must never block, and this module makes that an
architectural rule rather than a tuning exercise: nothing else in the codebase
calls `subprocess` directly. Output arrives line by line while the process runs,
a run can be cancelled and actually dies, and a run that overruns its deadline
is reported as overrun rather than waited on forever.

Nothing here imports the toolkit, so it is testable without a display. The app
layer is responsible for getting the callbacks onto the main loop.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# How long a process gets to exit on its own after being asked to stop, before it
# is killed. Long enough for `tofu` to release a state lock, short enough that
# cancelling still feels like cancelling.
GRACE_SECONDS = 5.0


class RunState(Enum):
    """Where a run got to. Every ending has a name; none of them is silence."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed out"


@dataclass(frozen=True)
class Result:
    """What a finished run produced."""

    command: tuple[str, ...]
    state: RunState
    returncode: int | None
    output: str
    seconds: float

    @property
    def ok(self) -> bool:
        return self.state is RunState.SUCCEEDED


class RunTimedOut(Exception):
    """A run passed its deadline, so there is no result to report."""

    def __init__(self, partial: Result) -> None:
        super().__init__(f"{' '.join(partial.command)} did not finish in {partial.seconds:.1f}s")
        self.partial = partial


@dataclass
class Run:
    """A subprocess in flight, and the handle used to watch or stop it."""

    command: tuple[str, ...]
    _process: subprocess.Popen[str]
    # The child's process group, read once while it is certainly alive. Never
    # looked up again: a reaped pid can belong to somebody else by then.
    _group: int | None = None
    _lines: list[str] = field(default_factory=list)
    _done: threading.Event = field(default_factory=threading.Event)
    _state: RunState = RunState.RUNNING
    _started: float = field(default_factory=time.perf_counter)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def state(self) -> RunState:
        with self._lock:
            return self._state

    @property
    def output(self) -> str:
        with self._lock:
            return "".join(self._lines)

    def cancel(self) -> None:
        """Stops the run, and makes sure it is actually stopped.

        The process is asked first and killed if it does not go. The whole group
        is signalled, because `tofu` spawns provider plugins and signalling only
        the parent leaves those running.
        """
        with self._lock:
            if self._state is not RunState.RUNNING:
                return
            self._state = RunState.CANCELLED
        self._stop()

    def stop_after_this_step(self) -> bool:
        """Asks the engine to finish what it is doing and start nothing more.

        **One SIGINT, and never an escalation.** That is what `tofu` reads as a
        graceful shutdown: the resource in flight completes, nothing further
        starts, and the state file is written before it exits. SIGTERM would
        take it mid-resource and leave the state describing infrastructure that
        has already changed — which is the one outcome an apply screen exists
        to prevent.

        The run keeps its own ending. This asks; the engine decides when.
        """
        with self._lock:
            if self._state is not RunState.RUNNING:
                return False
            group = self._group
        if group is None:
            return False
        try:
            os.killpg(group, signal.SIGINT)
        except (ProcessLookupError, PermissionError):
            return False
        return True

    def wait(self, timeout: float | None = None) -> Result:
        """Blocks until the run finishes. Never called from the interface."""
        if not self._done.wait(timeout):
            raise RunTimedOut(self._result())
        return self._result()

    def _stop(self) -> None:
        """Signals the child's own process group, and only ever that one.

        **The group is the one recorded when the process started.** Looking it
        up here instead — `os.getpgid(self._process.pid)` — reads the group of
        whatever holds that pid *now*, and a pid that has been reaped can be
        reused by anything, including this process. Signalling the group that
        comes back then kills us.

        The whole group is signalled because `tofu` spawns provider plugins and
        signalling only the parent leaves those running.
        """
        group = self._group
        if group is None:
            return
        for send, wait in ((signal.SIGTERM, GRACE_SECONDS), (signal.SIGKILL, GRACE_SECONDS)):
            if self._process.poll() is not None:
                return
            try:
                os.killpg(group, send)
            except (ProcessLookupError, PermissionError):
                return
            try:
                self._process.wait(timeout=wait)
                return
            except subprocess.TimeoutExpired:
                continue

    def _result(self) -> Result:
        with self._lock:
            return Result(
                command=self.command,
                state=self._state,
                returncode=self._process.returncode,
                output="".join(self._lines),
                seconds=time.perf_counter() - self._started,
            )


def start(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    timeout: float | None = None,
    environment: dict[str, str] | None = None,
    on_line: Callable[[str], None] | None = None,
    on_done: Callable[[Result], None] | None = None,
) -> Run:
    """Starts a command and returns at once.

    `command` is an argument list and never a shell string, so nothing a user
    typed can become a second command. `on_line` and `on_done` are called from a
    worker thread; a caller with an interface has to hand them to its main loop.
    """
    if not command:
        raise ValueError("a run needs a command")

    process = subprocess.Popen(  # noqa: S603
        list(command),
        cwd=str(cwd) if cwd else None,
        env={**os.environ, **(environment or {})},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        # Its own process group, so cancelling reaches the provider plugins too.
        start_new_session=True,
    )
    # `start_new_session=True` above makes the child a session leader, so its
    # group id is its pid — read now rather than when it is time to kill it.
    run = Run(command=tuple(command), _process=process, _group=process.pid)

    def pump() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            with run._lock:
                run._lines.append(line)
            if on_line is not None:
                on_line(line)
        process.wait()
        with run._lock:
            if run._state is RunState.RUNNING:
                run._state = RunState.SUCCEEDED if process.returncode == 0 else RunState.FAILED
        run._done.set()
        if on_done is not None:
            on_done(run._result())

    threading.Thread(target=pump, name="backsight-run", daemon=True).start()

    if timeout is not None:

        def deadline() -> None:
            if run._done.wait(timeout):
                return
            with run._lock:
                if run._state is not RunState.RUNNING:
                    return
                run._state = RunState.TIMED_OUT
            run._stop()

        threading.Thread(target=deadline, name="backsight-deadline", daemon=True).start()

    return run


@dataclass(frozen=True)
class Capture:
    """What a short command produced, with the two streams kept apart."""

    command: tuple[str, ...]
    returncode: int
    out: str
    err: str
    seconds: float

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def capture(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    stdin: str = "",
    timeout: float = 30.0,
    environment: dict[str, str] | None = None,
) -> Capture:
    """Runs a short command to completion and returns both streams separately.

    `start` merges stderr into stdout and streams it, which is right for a plan
    and wrong for a command whose answer is on one stream and whose complaint is
    on the other. Use this only for commands that finish quickly and produce
    little; it holds both streams in memory and blocks the caller's thread.
    """
    if not command:
        raise ValueError("a run needs a command")

    began = time.perf_counter()
    try:
        finished = subprocess.run(  # noqa: S603
            list(command),
            cwd=str(cwd) if cwd else None,
            env={**os.environ, **(environment or {})},
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as expired:
        raise RunTimedOut(
            Result(
                command=tuple(command),
                state=RunState.TIMED_OUT,
                returncode=None,
                output=_text(expired.stdout) + _text(expired.stderr),
                seconds=time.perf_counter() - began,
            )
        ) from expired

    return Capture(
        command=tuple(command),
        returncode=finished.returncode,
        out=finished.stdout,
        err=finished.stderr,
        seconds=time.perf_counter() - began,
    )


def _text(stream: str | bytes | None) -> str:
    if stream is None:
        return ""
    return stream if isinstance(stream, str) else stream.decode("utf-8", "replace")
