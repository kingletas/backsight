"""Colour lives in one module, and this is what keeps it there.

A hex code written into widget construction is the thing that makes
theming expensive later. It is cheap to prevent and a week to undo, so it is a
build failure rather than a convention.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "src" / "backsight" / "app"

# The one place allowed to name a colour. `tokens.py` is the design system's
# source of truth and the only file with literal values in it; everything else
# in the package reads them by name.
THEME = APP / "theme"

HEX = re.compile(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?(?:[0-9A-Fa-f]{2})?\b")
NAMED = re.compile(r"\b(?:rgba?|hsla?)\s*\(")


def widget_modules() -> list[Path]:
    return [p for p in sorted(APP.rglob("*.py")) if THEME not in p.parents]


def test_no_widget_module_names_a_colour():
    for path in widget_modules():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            found = HEX.search(line)
            assert not found, (
                f"{path.relative_to(ROOT)}:{number} names the colour {found.group()}. "
                "Colour belongs in app/theme/tokens.py, referenced by role."
            )


def test_no_widget_module_builds_a_colour_another_way():
    """A hex is the obvious spelling; `rgba(...)` is the one that gets past a grep."""
    for path in widget_modules():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            assert not NAMED.search(line), (
                f"{path.relative_to(ROOT)}:{number} builds a colour. "
                "Colour belongs in app/theme/tokens.py."
            )


def test_the_tokens_are_where_the_colours_actually_are():
    """A rule nothing violates because nothing is coloured is not a rule."""
    text = (THEME / "tokens.py").read_text(encoding="utf-8")
    assert len(HEX.findall(text)) >= 8


def test_the_component_sheet_names_no_colour_of_its_own():
    """It is hand-written; if a value is needed it goes in tokens.py."""
    css = (THEME / "components.css").read_text(encoding="utf-8")
    assert HEX.findall(css) == []
    assert not NAMED.search(css)


def test_both_editor_schemes_ship_as_data():
    """The editor scheme is a file, because GtkSourceView loads it from a path
    and because users bring their own."""
    schemes = THEME / "schemes"
    assert (schemes / "backsight-light.xml").is_file()
    assert (schemes / "backsight-dark.xml").is_file()
