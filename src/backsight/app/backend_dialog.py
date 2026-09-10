"""What it means that this workspace keeps its state on one laptop.

The row in the rail says `no backend`. This is what it opens: what was found,
what it costs, and the one honest thing to do about it today.

**There is no migrate button.** Migrating means writing a backend block and
running an init against a real bucket, and nothing here has been tested against
one. A button that cannot work is worse than none — it is the greyed Apply the
footer was rebuilt to remove.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.engine.workspace.backend import WITHOUT_A_BACKEND, LocalState

NOTHING_YET = "Nothing has been created yet, so there is no state to lose."
FOUND = "State found on this machine"
KEEP = "Keep it local for now"
HOW = (
    "Backsight cannot move it for you yet. Add a backend block to this module "
    "and run an init that migrates the state — the engine does the move, and it "
    "asks before it copies anything."
)


class BackendDialog(Adw.Dialog):
    """The `no backend` row, opened."""

    def __init__(self, module: str, state: LocalState | None, on_close: Callable | None = None):
        super().__init__()
        self._module = module
        self._state = state
        self._on_close = on_close
        self.set_content_width(420)
        self.set_title("Where this state lives")

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        for edge in ("top", "bottom", "start", "end"):
            getattr(body, f"set_margin_{edge}")(20)

        heading = Gtk.Label(label=f"{module} has no backend", xalign=0.0, wrap=True)
        heading.add_css_class("tf-title")
        body.append(heading)

        body.append(self._found())

        costs = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        for line in WITHOUT_A_BACKEND:
            said = Gtk.Label(label=f"· {line}", xalign=0.0, wrap=True)
            said.add_css_class("tf-small")
            said.add_css_class("tf-dim")
            costs.append(said)
        body.append(costs)

        how = Gtk.Label(label=HOW, xalign=0.0, wrap=True)
        how.add_css_class("tf-small")
        how.add_css_class("tf-faint")
        body.append(how)

        keep = Gtk.Button(label=KEEP)
        keep.add_css_class("tf-quiet")
        keep.set_halign(Gtk.Align.END)
        keep.connect("clicked", lambda *_: self.close())
        body.append(keep)
        self.set_focus(keep)

        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        view.set_content(body)
        self.set_child(view)

    def _found(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.add_css_class("tf-group")
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(0)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        for edge in ("top", "bottom", "start", "end"):
            getattr(inner, f"set_margin_{edge}")(10 if edge in ("top", "bottom") else 12)

        if self._state is None or self._state.is_empty:
            said = Gtk.Label(label=NOTHING_YET, xalign=0.0, wrap=True)
            said.add_css_class("tf-small")
            inner.append(said)
            box.append(inner)
            return box

        title = Gtk.Label(label=FOUND, xalign=0.0)
        title.add_css_class("tf-medium")
        inner.append(title)
        for text in (self._state.says(), str(self._state.path), _size(self._state.size)):
            line = Gtk.Label(label=text, xalign=0.0, wrap=True, selectable=True)
            # Selectable so the path can be copied, but never the first thing
            # focused — the dialog opened with its top line highlighted as if
            # something had been chosen.
            line.set_can_focus(False)
            line.add_css_class("tf-small")
            line.add_css_class("tf-faint")
            inner.append(line)
        box.append(inner)
        return box

    @property
    def says(self) -> list[str]:
        """Every line in the dialog, for a test that cannot present it."""
        return [
            *(
                [self._state.says(), str(self._state.path), _size(self._state.size)]
                if self._state is not None and not self._state.is_empty
                else [NOTHING_YET]
            ),
            *WITHOUT_A_BACKEND,
            HOW,
        ]


def _size(count: int) -> str:
    if count < 1024:
        return f"{count} bytes"
    if count < 1024 * 1024:
        return f"{count / 1024:.1f} KB"
    return f"{count / (1024 * 1024):.1f} MB"
