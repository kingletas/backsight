"""Run the interface on a display of its own, not on the person's screen.

Tests construct windows and activate actions that present dialogs; the smoke
drives a real window through two dozen views. All of it used the display the
person is working on — windows appearing over their work, stealing focus, and
taking the pointer with them.

Minimising them would be treating the symptom. A private X server means the
windows are never on their screen at all, and it costs one process.

Nothing here runs in the application itself. It is imported by the test suite
and the smoke, both of which call `use_a_private_display()` **before** anything
imports `gi` — GTK connects to a display when it is initialised, and by then
the choice has been made.
"""

from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import time
from pathlib import Path

# Displays to try. High numbers, because :0 and :1 belong to whoever is logged
# in and a collision would put the windows right back on their screen.
CANDIDATES = range(90, 200)

SIZE = "1280x820x24"

# How long the server gets to come up. It is a fraction of a second in
# practice; this is the point at which something is wrong rather than slow.
SECONDS = 10.0


class NoPrivateDisplay(RuntimeError):
    """No display of our own could be started, and the screen is not a fallback.

    **Falling back to whatever `DISPLAY` says is the one thing this must never
    do.** It did, and it put a test run's windows and dialogs onto the screen
    somebody was working on — which is the whole failure this module exists to
    prevent, arriving quietly through its own error path.
    """


_started: subprocess.Popen | None = None


def is_available() -> bool:
    return shutil.which("Xvfb") is not None


def use_a_private_display() -> str | None:
    """Points `DISPLAY` at a private X server, and returns which one.

    Raises `NoPrivateDisplay` rather than using the display already set.
    `BACKSIGHT_DISPLAY` is the deliberate way to choose one, and it is the only
    way this returns a display it did not start.
    """
    global _started

    chosen = os.environ.get("BACKSIGHT_DISPLAY")
    if chosen:
        # A deliberate choice wins. This is how somebody watches the smoke run.
        _use(chosen)
        return chosen

    if _started is not None:
        return os.environ.get("DISPLAY")

    server_path = shutil.which("Xvfb")
    if server_path is None:
        raise NoPrivateDisplay(
            "Xvfb is not installed, so there is nowhere to put these windows "
            "but the screen somebody is using. Install it, or set "
            "BACKSIGHT_DISPLAY deliberately."
        )

    for number in CANDIDATES:
        display = f":{number}"
        if Path(f"/tmp/.X{number}-lock").exists():  # noqa: S108 — X's own path
            continue
        server = subprocess.Popen(  # noqa: S603
            # The full path, resolved once: a partial name is whatever `PATH`
            # happens to hold when this runs.
            # `-terminate` makes the server exit when its last client goes.
            # `atexit` cannot run when a process is killed, and a run killed
            # part-way used to leave a server behind for good — enough of them
            # and there is no free display left to start on.
            [server_path, display, "-screen", "0", SIZE, "-nolisten", "tcp", "-terminate"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if _came_up(server, number):
            _started = server
            atexit.register(stop)
            _use(display)
            return display
        server.kill()
        server.wait(timeout=SECONDS)
    raise NoPrivateDisplay(
        f"no free display between :{CANDIDATES.start} and :{CANDIDATES.stop - 1}"
    )


def _use(display: str) -> None:
    """Points the toolkit at one X display, and makes sure it looks at X at all.

    **This is the part that actually contains anything.** GTK4 prefers Wayland
    whenever `WAYLAND_DISPLAY` is set, and on a Wayland session it is — so
    setting `DISPLAY` alone starts a private X server that nothing ever
    connects to, and every window still opens on the compositor the person is
    working in. The private display was real, running, and unused.

    `wmctrl` and friends are X11-only, so a watcher on `DISPLAY=:0` sees
    nothing either, and the windows look like they came from nowhere.
    """
    os.environ["DISPLAY"] = display
    os.environ["GDK_BACKEND"] = "x11"
    # Removed rather than blanked: GTK checks whether the variable is set.
    os.environ.pop("WAYLAND_DISPLAY", None)


def stop() -> None:
    """Stops the private server. Registered with `atexit`, so it always runs."""
    global _started
    if _started is None:
        return
    _started.terminate()
    try:
        _started.wait(timeout=SECONDS)
    except subprocess.TimeoutExpired:
        _started.kill()
    _started = None


def _came_up(server: subprocess.Popen, number: int) -> bool:
    """Waits for the lock file, which is X saying it is ready to be connected to."""
    lock = Path(f"/tmp/.X{number}-lock")  # noqa: S108 — X's own path
    deadline = time.perf_counter() + SECONDS
    while time.perf_counter() < deadline:
        if server.poll() is not None:
            # It exited, so that display was taken after all.
            return False
        if lock.exists():
            return True
        time.sleep(0.02)
    return False
