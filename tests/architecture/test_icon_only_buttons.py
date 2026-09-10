"""An icon with no words needs words somewhere.

A button whose whole content is a glyph reads as nothing to a screen reader and
as a guess to anybody who has not used the app before. GTK exposes the tooltip
as the accessible description, so requiring one covers both.

Source-level, deliberately: walking a live window also finds libadwaita's own
internal buttons, which are not ours to label.
"""

from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "src" / "backsight" / "app"

# `Gtk.Button(icon_name=...)`, `Gtk.MenuButton(icon_name=...)` and friends, up
# to the closing bracket of that call.
ICON_BUTTON = re.compile(
    r"(?:(?P<name>[\w.]+)\s*=\s*)?(?:Gtk|Adw)\.(?:Menu|Toggle|Split)?Button"
    r"(?:\.new_from_icon_name)?\((?P<arguments>[^()]*icon_name[^()]*)\)",
    re.DOTALL,
)


def test_every_icon_only_button_says_what_it_does():
    unnamed = []
    for source in sorted(APP.rglob("*.py")):
        text = source.read_text(encoding="utf-8")
        for found in ICON_BUTTON.finditer(text):
            arguments = found.group("arguments")
            if "label=" in arguments or "tooltip_text=" in arguments:
                continue
            # Set on a following line, which is just as good for the reader.
            name = found.group("name")
            if name and f"{name}.set_tooltip_text(" in text:
                continue
            line = text[: found.start()].count("\n") + 1
            unnamed.append(f"{source.relative_to(APP)}:{line}")
    assert not unnamed, f"icon-only buttons with nothing to read: {unnamed}"
