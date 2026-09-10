"""Nothing in this application communicates state by moving.

`reduce motion` is a setting somebody turns on because motion costs them
something, and honouring it by making animations shorter is not honouring it.
The answer here is not a setting at all: the surfaces that would animate do not.

The editor is the sharp case. A caret, a gutter mark, a spine and a change map
that ease into place are things you watch instead of read, and the whole design
rests on the gutter being the cheapest thing on the screen.
"""

from __future__ import annotations

import re
from pathlib import Path

SHEET = (
    Path(__file__).resolve().parents[2] / "src" / "backsight" / "app" / "theme" / "components.css"
)


def test_no_component_animates_anything():
    """A transition in the stylesheet is motion nobody asked for, and the one
    place it would land is the editor."""
    css = SHEET.read_text(encoding="utf-8")
    said = re.findall(r"^\s*(transition|animation)[^;]*;", css, re.MULTILINE)
    assert said == [], "the stylesheet animates: " + ", ".join(said)


def test_the_drawer_has_no_transition_to_turn_off():
    """An `Adw.ViewStack` has none, which is why it is the widget for this —
    a `Gtk.Stack` has to be told, and being told is a thing to forget."""
    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw

    assert not [name for name in dir(Adw.ViewStack) if "transition" in name]
