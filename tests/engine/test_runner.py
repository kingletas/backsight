"""The async boundary: nothing waits, cancelling kills, overrunning is reported."""

import os
import signal
import sys
import time

import pytest

from backsight.engine.runner import process
from backsight.engine.runner.process import RunState, RunTimedOut

# Long enough that a blocking implementation is unmistakable, short enough that
# the suite stays quick.
SLOW = 5.0


def python(script: str) -> list[str]:
    return [sys.executable, "-u", "-c", script]


def test_starting_a_slow_run_returns_immediately():
    started = time.perf_counter()
    run = process.start(python(f"import time; time.sleep({SLOW})"))
    elapsed = time.perf_counter() - started
    assert elapsed < 0.5, f"start() blocked for {elapsed:.2f}s"
    assert run.state is RunState.RUNNING
    run.cancel()


def test_output_arrives_while_the_process_is_still_running():
    seen = []
    run = process.start(
        python("import time\nfor i in range(3):\n    print(i)\n    time.sleep(0.2)"),
        on_line=seen.append,
    )
    # One line at least should arrive before the process is anywhere near done.
    deadline = time.perf_counter() + 2.0
    while not seen and time.perf_counter() < deadline:
        time.sleep(0.02)
    assert seen, "no output arrived while the process was running"
    assert run.state is RunState.RUNNING
    run.wait(5)


def test_a_successful_run_reports_its_output_and_state():
    result = process.start(python("print('hello')")).wait(5)
    assert result.ok
    assert result.state is RunState.SUCCEEDED
    assert result.returncode == 0
    assert result.output.strip() == "hello"


def test_a_failing_run_is_a_result_and_not_an_exception():
    """A non-zero exit is an answer. Only having no answer is exceptional."""
    result = process.start(python("import sys; print('bad'); sys.exit(3)")).wait(5)
    assert not result.ok
    assert result.state is RunState.FAILED
    assert result.returncode == 3
    assert "bad" in result.output


def test_cancelling_actually_kills_the_process():
    run = process.start(python(f"import time; time.sleep({SLOW})"))
    pid = run._process.pid
    time.sleep(0.2)
    run.cancel()
    result = run.wait(10)
    assert result.state is RunState.CANCELLED
    assert not alive(pid), "the process outlived its cancellation"


def test_cancelling_kills_the_children_as_well():
    """`tofu` spawns provider plugins; signalling only the parent orphans them."""
    script = (
        "import subprocess, sys, time\n"
        f"child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep({SLOW})'])\n"
        "print(child.pid, flush=True)\n"
        f"time.sleep({SLOW})\n"
    )
    lines: list[str] = []
    run = process.start(python(script), on_line=lines.append)
    deadline = time.perf_counter() + 5.0
    while not lines and time.perf_counter() < deadline:
        time.sleep(0.02)
    assert lines, "the child never reported its pid"
    child_pid = int(lines[0].strip())
    run.cancel()
    run.wait(10)
    time.sleep(0.3)
    assert not alive(child_pid), "the child outlived its parent's cancellation"


def test_a_run_that_overruns_is_reported_as_overrun():
    run = process.start(python(f"import time; time.sleep({SLOW})"), timeout=0.4)
    result = run.wait(10)
    assert result.state is RunState.TIMED_OUT
    assert not result.ok
    assert not alive(run._process.pid)


def test_waiting_longer_than_allowed_raises_and_carries_what_it_has():
    run = process.start(python(f"import time; print('early', flush=True); time.sleep({SLOW})"))
    with pytest.raises(RunTimedOut) as raised:
        run.wait(0.5)
    assert raised.value.partial.state is RunState.RUNNING
    run.cancel()


def test_a_command_is_an_argument_list_and_never_a_shell_string():
    """Nothing a user typed may become a second command."""
    result = process.start(["echo", "one; echo two"]).wait(5)
    assert result.output.strip() == "one; echo two"


def test_an_empty_command_is_refused():
    with pytest.raises(ValueError):
        process.start([])


def test_cancelling_a_finished_run_changes_nothing():
    run = process.start(python("print('done')"))
    result = run.wait(5)
    run.cancel()
    assert run.state is result.state is RunState.SUCCEEDED


def alive(pid: int) -> bool:
    """Whether a process still exists, ignoring whether it has been reaped."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
            return handle.read().split(")")[-1].split()[0] != "Z"
    except FileNotFoundError:
        return False


def test_the_liveness_helper_is_not_lying():
    """A check that always says 'dead' would make every test above pass."""
    run = process.start(python(f"import time; time.sleep({SLOW})"))
    time.sleep(0.2)
    assert alive(run._process.pid)
    os.killpg(os.getpgid(run._process.pid), signal.SIGKILL)
    run.wait(5)
    assert not alive(run._process.pid)
