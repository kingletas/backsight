"""Every shortcut the application installs reaches an action the window has.

`Ctrl+O` was printed on the workspace switcher as the way to open a workspace,
and no command in the keymap carried it — so the first shortcut anybody reaches
for on an empty window did nothing, and the app had told them to press it.

`F11` is asked for by name in `requirements.md` and was not bound either.
"""

from __future__ import annotations

import pytest

from backsight.engine.settings.keys import Keymap

# The ones whose absence reads as "shortcuts do not work" rather than as a
# missing feature. Every editor has them and every hand reaches for them.
EVERYDAY = {
    "open-workspace": "<Control>o",
    "new-file": "<Control>n",
    "save": "<Control>s",
    "save-as": "<Control><Shift>s",
    "close-tab": "<Control>w",
    "find": "<Control>f",
    "replace": "<Control>h",
    "goto-line": "<Control>l",
    "full-screen": "F11",
    "settings": "<Control>comma",
}


def test_the_everyday_shortcuts_are_bound():
    keymap = Keymap.build()
    for action, accelerator in EVERYDAY.items():
        command = keymap.commands.get(action)
        assert command is not None, f"{action} is not in the keymap at all"
        assert command.accelerator == accelerator, f"{action} is {command.accelerator}"


def test_no_two_commands_want_the_same_key():
    """One of them would silently lose, and nothing would say which."""
    assert Keymap.build().conflicts() == []


def test_every_installed_shortcut_reaches_an_action_the_window_has():
    """An accelerator on `win.<something the window never registered>` is a key
    that does nothing, and nothing in the toolkit reports it."""
    gi = pytest.importorskip("gi", reason="the toolkit is not installed")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")

    from gi.repository import Gtk

    from backsight.app.application import Application
    from backsight.app.window import Window

    # Reuse whatever application this process already has. A second
    # `Adw.Application` in one process shares GTK's global accel map and its
    # own registration state, and building one while another exists made this
    # pass alone and fail inside the suite.
    application = Gtk.Application.get_default() or Application()
    if not isinstance(application, Application):
        application = Application()
    installed = application.install_shortcuts()
    live = set(Window(application=application).list_actions())

    nowhere = sorted(action for action in installed if action not in live)
    assert nowhere == [], "shortcuts bound to nothing: " + ", ".join(nowhere)
    assert len(installed) >= len(EVERYDAY)


def test_apply_has_no_shortcut_and_that_is_deliberate():
    """The one irreversible thing in the product. A key that reaches it from
    anywhere makes it something a hand can do by itself."""
    assert Keymap.build().commands["apply"].accelerator is None
