"""Escape, in one place, for every surface this application opens.

Two failures produced this file and they are the same failure at two depths.

**The first**: the stacks view was modal, had no header bar and so no close
button, and nothing listened for Escape — so opening it locked the application
and the only way out was to kill it. That is the worst thing an interface can
do, and it was one line of missing wiring.

**The second is subtler and is why this stopped being three lines.** The command
palette *did* listen for Escape, on a controller attached to its window, and
Escape still did nothing. The reason is that its search field has the keyboard,
and `Gtk.SearchEntry` installs its own Escape shortcut — it emits `stop-search`
and **stops the event**, so a controller on the window never runs. Every surface
in this application whose first control is a text field had the same hole, and
each of them looked correctly wired.

So the rule is **capture, not bubble**. The window sees Escape before any child
does, decides, and says so — which is also what makes the rest of the promises
keepable:

- **The topmost modal closes**, because only the focused window gets the key.
- **Nested modals close inside-out**, for the same reason, one press each.
- **Nothing leaks underneath**: handling it returns `True` and the press is over,
  so no global shortcut fires behind a modal that just closed.
- **Focus comes back to where it was**, because the surface remembers what had
  it before it opened.
- **A destructive question can opt out**, because *escaping* an irreversible
  choice is not the same as answering it.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gtk


def escape_closes(
    surface: Gtk.Widget,
    *,
    close: Callable[[], bool | None] | None = None,
) -> Gtk.EventControllerKey:
    """Makes Escape reach `surface` before anything inside it can eat the key.

    `close` returns falsey to say *not mine* — which lets one surface hold
    several things that Escape dismisses in order, and lets the press fall
    through when it holds none of them.
    """
    keys = Gtk.EventControllerKey()
    # **Capture.** A `Gtk.SearchEntry`, a `Gtk.Text` with a selection and an
    # open popover all consume Escape at the bubble phase, and a controller on
    # the window is the last thing to see it rather than the first.
    keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

    def pressed(_controller, keyval: int, _code: int, _state) -> bool:
        if keyval != Gdk.KEY_Escape:
            return False
        if close is None:
            surface.close()
            return True
        return bool(close())

    keys.connect("key-pressed", pressed)
    surface.add_controller(keys)
    return keys


def remembers_focus(window: Gtk.Window, parent: Gtk.Window | None) -> None:
    """Puts the keyboard back where it was when this window closes.

    GTK returns focus to the transient parent and stops there — which leaves it
    on whatever that window last focused, and after a modal that is usually the
    control that opened the modal rather than the buffer somebody was typing
    in. Remembering is four lines and it is the difference between coming back
    to your work and going and finding it.
    """
    if parent is None:
        return
    was = parent.get_focus()
    if was is None:
        return

    def restore(*_args) -> None:
        if was.get_root() is not None:
            was.grab_focus()

    window.connect("close-request", lambda *_a: (restore(), False)[1])
    window.connect("unrealize", restore)


def dismissable(
    window: Adw.Window,
    content: Gtk.Widget,
    *,
    title: str = "",
    parent: Gtk.Window | None = None,
) -> None:
    """Gives a window a title bar, a close button and an Escape that works.

    Both, always. A header bar without Escape makes somebody reach for a mouse
    they may not have; Escape without a header bar leaves nothing to point at
    for anybody who does not know the key.
    """
    header = Adw.HeaderBar()
    if title:
        header.set_title_widget(Adw.WindowTitle(title=title))

    layout = Adw.ToolbarView()
    layout.add_top_bar(header)
    layout.set_content(content)
    window.set_content(layout)

    escape_closes(window)
    remembers_focus(window, parent or window.get_transient_for())
