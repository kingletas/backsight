"""Every action the window registers can actually be activated.

This is the test that was missing. `open-workspace` shipped pointing at a
button handler that takes the button as an argument, so choosing it from the
menu raised a `TypeError` and the workspace could not be opened at all. The
architecture test said the name existed and the wiring test activated a chosen
few; neither touched that one.

Nothing here asserts what an action *does* — only that invoking it reaches its
handler. That is the class of bug this catches, and it is the class that
reaches a user as "the application does not work".
"""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.window import Window  # noqa: E402

# Ends this window or opens another. Activating either would take the test
# process with it, and neither is what this is checking.
LIFECYCLE = {"close-window", "full-screen", "open-in-new-window", "move-to-new-window"}

# Takes a target, so activating it with none is a misuse rather than a defect.
PARAMETERISED = {"panel"}

# Anything that reaches the desktop rather than drawing its own window.
#
# `Gtk.FileDialog` is **portal-backed**: it does not draw a window in this
# process at all, it asks xdg-desktop-portal in the person's session to show a
# file chooser. `Gio.AppInfo.launch*` starts their file manager or terminal the
# same way. Neither is on our `DISPLAY`, so no private X server can contain
# them — activating these in a test puts windows on the screen somebody is
# working at, and there is no display setting that prevents it.
#
# They are excluded because a test has no business opening somebody's file
# chooser, not because they might fail.
REACHES_THE_DESKTOP = {
    "open-workspace",
    "open-file",
    "open-settings-folder",
    "open-containing-folder",
    "open-terminal-here",
}

SKIP = LIFECYCLE | PARAMETERISED | REACHES_THE_DESKTOP


def names(window: Window) -> list[str]:
    return sorted(name for name in window.list_actions() if name not in SKIP)


def sweep(window: Window, capsys) -> list[str]:
    """Activates every action and returns the ones that raised.

    One window for all of them: a window per action was 119 windows in a single
    run and the suite was killed for memory.
    """
    capsys.readouterr()
    broken: list[str] = []
    for name in names(window):
        window.activate_action(f"win.{name}", None)
        printed = capsys.readouterr().err
        if "Traceback" in printed:
            broken.append(f"win.{name}:\n{printed}")
    return broken


def test_there_are_actions_to_check():
    """A sweep over an empty list would pass and prove nothing."""
    assert len(names(Window())) > 100


def test_every_action_reaches_its_handler(capsys):
    """With no workspace open. Most report that; none may fail.

    An exception inside a GObject handler does not propagate: PyGObject prints
    it and carries on, so `activate_action` returns normally and the action
    silently does nothing. Reading stderr is the only way to see it, and that
    is precisely why the broken one shipped.
    """
    broken = sweep(Window(), capsys)
    assert broken == [], "\n".join(broken)


def test_every_action_survives_a_workspace_being_open(capsys):
    """The other half: a handler that only fails once there is something to act on.

    This found `select-all`, which is a signal taking a boolean and was being
    emitted bare.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "fixtures" / "workspace"
    window = Window()
    window.open_workspace(root)
    window.open_file(sorted(root.rglob("*.tf"))[0])
    broken = sweep(window, capsys)
    assert broken == [], "\n".join(broken)


def test_the_actions_that_reach_the_desktop_still_reach_their_handler(monkeypatch, capsys):
    """The excluded ones still need cover — `open-workspace` is why this exists.

    It shipped pointing at a button handler that takes the button as an
    argument. Activating it here would open the person's file chooser through
    the portal, so the portal is replaced and only the handler runs.
    """
    from gi.repository import Gio, Gtk

    asked: list[str] = []

    class Chooser:
        def __init__(self, **_kwargs):
            pass

        def select_folder(self, *_args):
            asked.append("select_folder")

        def open(self, *_args):
            asked.append("open")

    monkeypatch.setattr(Gtk, "FileDialog", Chooser)
    monkeypatch.setattr(
        Gio.AppInfo, "launch_default_for_uri", staticmethod(lambda *_a: asked.append("launch"))
    )
    monkeypatch.setattr(Gio.AppInfo, "get_default_for_type", staticmethod(lambda *_a: None))

    window = Window()
    capsys.readouterr()
    for name in sorted(REACHES_THE_DESKTOP):
        window.activate_action(f"win.{name}", None)
        printed = capsys.readouterr().err
        assert "Traceback" not in printed, f"win.{name} raised:\n{printed}"
    assert asked, "the handlers were reached but none of them did anything"
