"""Cancelling a run signals that run, and nothing else.

A process group is looked up once, while the child is certainly alive. Doing it
at kill time reads the group of whatever holds that pid *now* — and a pid that
has been reaped can belong to anything, including this process. The suite was
being SIGKILLed roughly one run in three.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from backsight.engine.runner.process import start


def test_the_group_is_recorded_when_the_process_starts():
    run = start([sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        assert run._group == run._process.pid
        assert os.getpgid(run._process.pid) == run._group
    finally:
        run.cancel()


def test_a_reaped_process_is_never_looked_up_again():
    """The bug: after this pid is gone, its group must not be consulted."""
    run = start([sys.executable, "-c", "pass"])
    run.wait(timeout=10)
    recorded = run._group
    # Whatever holds that pid now is somebody else's business.
    run.cancel()
    assert run._group == recorded


def test_cancelling_kills_the_child_and_not_the_caller():
    """The whole point, said as a behaviour."""
    run = start([sys.executable, "-c", "import time; time.sleep(30)"])
    child = run._process.pid
    run.cancel()
    deadline = time.perf_counter() + 10
    while time.perf_counter() < deadline:
        if run._process.poll() is not None:
            break
        time.sleep(0.05)
    assert run._process.poll() is not None
    assert not _alive(child)
    assert _alive(os.getpid()), "we are still here"


def test_the_child_gets_a_session_of_its_own():
    """Otherwise signalling its group would reach ours."""
    run = start([sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        assert os.getpgid(run._process.pid) != os.getpgid(os.getpid())
    finally:
        run.cancel()


def test_cancelling_a_run_that_already_finished_signals_nothing():
    run = start([sys.executable, "-c", "pass"])
    run.wait(timeout=10)
    run.cancel()
    assert _alive(os.getpid())


def test_a_provider_plugin_goes_with_its_parent():
    """`tofu` spawns plugins; signalling only the parent leaves those running."""
    script = (
        "import subprocess, sys, time;"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']);"
        "time.sleep(30)"
    )
    run = start([sys.executable, "-c", script])
    time.sleep(0.6)
    group = run._group
    run.cancel()
    time.sleep(0.4)
    assert not _group_alive(group)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _group_alive(group: int) -> bool:
    found = subprocess.run(
        ["ps", "-o", "pid=", "-g", str(group)], capture_output=True, text=True, check=False
    )
    return bool(found.stdout.strip())
