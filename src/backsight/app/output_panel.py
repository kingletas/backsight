"""Whatever the engine last printed, verbatim.

The friendly summary is a convenience and never a replacement: an expert who
cannot check it against the real output does not trust the summary, and a
translated error with no way back to the original is a different opacity rather
than less of it.

This is the somewhere-reachable half of that. It is not the console — the
console is for asking a question, and this is for reading the answer to one
that was already asked.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

EMPTY = "Whatever the engine prints will appear here."

# Past this it scrolls inside itself rather than taking the window with it.
HEIGHT = 260


class OutputPanel(Adw.Bin):
    """One block of text, selectable, and a line saying so when there is none."""

    def __init__(self) -> None:
        super().__init__()
        self._text = Gtk.Label(xalign=0.0, yalign=0.0, selectable=True, wrap=True)
        self._text.add_css_class("tf-mono")
        self._text.add_css_class("tf-small")
        self._text.set_visible(False)

        self._empty = Gtk.Label(label=EMPTY, xalign=0.0)
        self._empty.add_css_class("tf-small")
        self._empty.add_css_class("tf-faint")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.append(self._empty)
        box.append(self._text)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_propagate_natural_height(True)
        scroller.set_max_content_height(HEIGHT)
        scroller.set_child(box)
        for edge in ("top", "bottom", "start", "end"):
            getattr(scroller, f"set_margin_{edge}")(10 if edge in ("top", "bottom") else 12)
        self._scroller = scroller
        self.set_child(scroller)

    @property
    def text(self) -> str:
        return self._text.get_text()

    def show(self, text: str) -> None:
        """Replaces what is there. The last thing run is what somebody wants."""
        said = text.rstrip()
        self._text.set_text(said)
        self._text.set_visible(bool(said))
        self._empty.set_visible(not said)
        adjustment = self._scroller.get_vadjustment()
        adjustment.set_value(adjustment.get_lower())

    def clear(self) -> None:
        self.show("")
