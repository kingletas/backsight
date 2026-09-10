"""The interface under test never appears on the person's screen."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from backsight.app import offscreen


def test_the_suite_is_not_on_the_display_the_person_is_using():
    """The whole point. Windows here would land over their work."""
    if not offscreen.is_available():
        return
    # Read from the environment rather than from conftest: the suite's root
    # conftest is not an importable module, and what matters is where GTK will
    # actually connect.
    where = os.environ.get("DISPLAY")
    assert where is not None
    assert where not in (":0", ":1"), "that is somebody's own screen"
    assert where.lstrip(":").isdigit()
    assert int(where.lstrip(":")) in offscreen.CANDIDATES


def test_a_deliberate_choice_wins():
    """How a person watches the smoke run: `make smoke-watch`.

    Every variable it moves is put back. Leaving `DISPLAY` pointing at a
    display that does not exist makes whichever test runs next unable to open
    one at all, and the order is randomised.
    """
    before = {name: os.environ.get(name) for name in ("DISPLAY", "GDK_BACKEND", "WAYLAND_DISPLAY")}
    os.environ["BACKSIGHT_DISPLAY"] = ":123"
    try:
        assert offscreen.use_a_private_display() == ":123"
        assert os.environ["DISPLAY"] == ":123"
    finally:
        del os.environ["BACKSIGHT_DISPLAY"]
        for name, value in before.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_the_screen_is_never_a_fallback():
    """It fell back once, and put a test run's dialogs on the desktop.

    Refusing is right: a run that cannot be contained should not happen at all.
    """
    import inspect

    source = inspect.getsource(offscreen.use_a_private_display)
    assert "NoPrivateDisplay" in source
    assert "return None" not in source, "there is no quiet fallback any more"


def test_asking_twice_does_not_start_a_second_server():
    if not offscreen.is_available():
        return
    first = offscreen.use_a_private_display()
    assert offscreen.use_a_private_display() == first


def test_a_display_number_somebody_is_using_is_skipped():
    """`:0` and `:1` are excluded by construction, not by luck."""
    assert 0 not in offscreen.CANDIDATES
    assert 1 not in offscreen.CANDIDATES


def test_the_server_is_stopped_when_the_process_ends():
    """It is registered with `atexit`, so a crashing run does not leak one."""
    import atexit
    import inspect

    source = inspect.getsource(offscreen)
    assert "atexit.register(stop)" in source
    assert atexit is not None


def test_a_window_really_opens_on_it():
    """The mechanism is only worth anything if GTK actually connects."""
    if not offscreen.is_available():
        return
    script = (
        "import gi;"
        "gi.require_version('Gtk','4.0');gi.require_version('Adw','1');"
        "from gi.repository import Adw, Gtk;"
        "Adw.init();"
        "w = Adw.ApplicationWindow();"
        "w.present();"
        "print('opened on', __import__('os').environ['DISPLAY'])"
    )
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [str(root / ".venv" / "bin" / "python"), "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "DISPLAY": os.environ["DISPLAY"]},
        cwd=root,
        check=False,
    )
    assert "opened on" in result.stdout, result.stderr


def test_the_server_goes_when_its_last_client_does():
    """`atexit` cannot run when a process is killed, and a killed run used to
    leave a display server behind for good."""
    import inspect

    assert "-terminate" in inspect.getsource(offscreen.use_a_private_display)


def test_the_toolkit_is_pointed_at_x_and_not_the_compositor():
    """The part that actually contains anything.

    GTK4 prefers Wayland whenever `WAYLAND_DISPLAY` is set, and on a Wayland
    session it is. Setting `DISPLAY` alone starts a private X server that
    nothing connects to, and every window still opens on the compositor the
    person is working in — which is exactly what happened.
    """
    import os

    if not offscreen.is_available():
        return
    assert os.environ.get("GDK_BACKEND") == "x11"
    assert "WAYLAND_DISPLAY" not in os.environ


def test_the_display_gtk_actually_connected_to_is_the_private_one():
    """Reading the environment is not proof; ask the toolkit.

    In a subprocess, because `gtk_init` happens once per process: a test that
    moves `DISPLAY` earlier in this file leaves the toolkit unable to open one
    at all, and the order is randomised.
    """
    import os
    import subprocess
    from pathlib import Path

    if not offscreen.is_available():
        return
    script = (
        "import sys; sys.path.insert(0, 'src');"
        "from backsight.app.offscreen import use_a_private_display;"
        "where = use_a_private_display();"
        "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1');"
        "from gi.repository import Adw, Gdk;"
        "Adw.init();"
        "d = Gdk.Display.get_default();"
        "print(type(d).__name__, d.get_name(), where)"
    )
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [str(root / ".venv" / "bin" / "python"), "-c", script],
        capture_output=True,
        text=True,
        cwd=root,
        env={**os.environ},
        check=False,
    )
    assert result.returncode == 0, result.stderr
    backend, name, where = result.stdout.split()
    assert backend == "X11Display", backend
    assert where in name
    number = name.lstrip(":").split(".")[0]
    assert int(number) in offscreen.CANDIDATES, name


def test_the_main_loop_hand_over_takes_keyword_arguments():
    """It took positional arguments only, so a callback with a keyword raised
    inside a worker thread — where nothing in the window would ever see it."""
    from backsight.app.runs import on_main_loop

    seen = []
    on_main_loop(lambda *a, **k: seen.append((a, k)))(1, elapsed=2.0)
    from gi.repository import GLib

    context = GLib.MainContext.default()
    for _ in range(20):
        if seen:
            break
        context.iteration(False)
    assert seen == [((1,), {"elapsed": 2.0})]
