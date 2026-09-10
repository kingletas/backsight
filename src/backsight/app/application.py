"""The application object, which exists to own the window and the shortcuts."""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk

from backsight.app.theme import Theme
from backsight.app.window import Window
from backsight.engine.settings.keys import Keymap

APPLICATION_ID = "com.kingletas.Backsight"

# The icon has to be named for the application id or it will not resolve, and
# GTK falls back to the generic document glyph — which reads as unfinished
# software. The search path is added so it works from a source tree too, not
# only from an installed prefix.
ICONS = Path(__file__).resolve().parents[3] / "data" / "icons"

# A second key for the same command, where a keyboard makes one of them
# awkward. `Ctrl+=` is the one people reach for and `Ctrl++` is the one they
# describe, and on many layouts they are the same physical press.
ALSO = {
    "zoom-in": ("<Control>plus", "<Control><Shift>equal"),
    "zoom-out": ("<Control>KP_Subtract",),
    "zoom-reset": ("<Control>KP_0",),
}


class Application(Adw.Application):
    def __init__(self, workspace: Path | None = None) -> None:
        super().__init__(
            application_id=APPLICATION_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self._workspace = workspace
        # The search path is the theme's; this only names what to look for.
        Gtk.Window.set_default_icon_name(APPLICATION_ID)
        self.install_shortcuts()

    def install_shortcuts(self, keymap: Keymap | None = None) -> dict[str, list[str]]:
        """Binds every command in the keymap, and returns what was bound.

        The keymap has always described the bindings — the menus and the
        keyboard reference read it — and **nothing installed them**. Only
        `win.save` was ever bound, so every other shortcut in the application
        was a line in a document.
        """
        found = keymap or Keymap.build()
        installed: dict[str, list[str]] = {}
        for command in found.commands.values():
            if not command.accelerator:
                continue
            keys = [command.accelerator, *ALSO.get(command.action, ())]
            self.set_accels_for_action(f"win.{command.action}", keys)
            installed[command.action] = keys
        return installed

    def do_startup(self) -> None:
        """The stylesheets go in before any window is built.

        Stock widgets keep libadwaita's own greys until the token sheet is
        installed, so a window constructed first draws once in them.
        """
        Adw.Application.do_startup(self)
        Theme.shared()

    def do_command_line(self, _command_line: Gio.ApplicationCommandLine) -> int:
        self.activate()
        return 0

    def do_activate(self) -> None:
        window = self.props.active_window or Window(application=self)
        window.connect("close-request", self._on_close)
        if self._workspace is not None and window.workspace is None:
            window.open_workspace(self._workspace)
        window.present()
        # After presenting, so the offer has a window to appear in.
        window.offer_what_was_left_behind()

    def _on_close(self, window: Window) -> bool:
        """Writes down where somebody was, then lets the window go.

        False, always: this records state, it never refuses a close. A prompt
        about unsaved files is the tab's job and happens before this.
        """
        window.closing()
        return False
