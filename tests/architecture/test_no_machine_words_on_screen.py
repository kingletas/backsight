"""Nothing a person reads is a token we made up to store something under.

Preferences showed values reading `single_click` and `after_current`, because
the stored value was put on screen unchanged. They are our storage, not words.

This checks what is handed to a label, a title, a subtitle or a tooltip — the
places a string becomes something somebody reads. It cannot see a token that
arrives through a variable, so it is a floor rather than a proof; the sweep that
found the rest is in the commit that removed them.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[2] / "src" / "backsight" / "app"

# Two or more lowercase runs joined by underscores: `single_click`, `follow_system`.
TOKEN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")

# Where a string turns into something read.
SHOWN = {
    "label",
    "title",
    "subtitle",
    "text",
    "placeholder_text",
    "tooltip_text",
    "heading",
    "body",
}
SETTERS = {f"set_{name}" for name in SHOWN}


def _is_a_token(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and bool(TOKEN.match(node.value))
    )


def _offences(tree: ast.AST, name: str) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg in SHOWN and _is_a_token(keyword.value):
                found.append(f"{name}:{node.lineno} {keyword.arg}={keyword.value.value!r}")
        method = node.func.attr if isinstance(node.func, ast.Attribute) else ""
        if method in SETTERS and node.args and _is_a_token(node.args[0]):
            found.append(f"{name}:{node.lineno} {method}({node.args[0].value!r})")
    return sorted(found)


def _across_the_application() -> list[str]:
    found = []
    for path in APP.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found.extend(_offences(tree, path.name))
    return sorted(found)


def test_no_stored_token_is_handed_to_something_that_shows_it():
    offences = _across_the_application()
    assert not offences, "machine words on screen: " + "; ".join(offences)


def test_it_can_say_otherwise():
    """A green check that has never gone red proves nothing about the red."""
    caught = _offences(
        ast.parse(
            "Adw.ComboRow(title='Open with', subtitle='single_click')\n"
            "row.set_label('after_current')\n"
            "Gtk.Label(label='Open a file with')\n"
            "widget.add_css_class('tf_rail_heading')\n"
        ),
        "made-up.py",
    )
    assert len(caught) == 2
    assert any("single_click" in said for said in caught)
    assert any("after_current" in said for said in caught)
