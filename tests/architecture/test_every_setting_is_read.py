"""A setting offered in Preferences is read by something.

Twenty-one of the thirty-eight were read by nothing at all: the window wrote
them to a file, the file was loaded on the next launch, and no line of code ever
asked for the value. Every one of those switches moved and changed nothing.

A control that does nothing is worse than a missing one — it spends the trust
the rest of the window is built on, and it cannot be found by reading the
dialog, because the dialog is the half that works.
"""

from __future__ import annotations

import ast
from pathlib import Path

from backsight.app.settings_dialog import GROUPS
from backsight.engine.settings.layers import DEFAULTS

SOURCE = Path(__file__).resolve().parents[2] / "src" / "backsight"

# The two files that hold every key by definition: the defaults themselves, and
# the dialog that lists them. Reading a key here is not consuming it.
DECLARING = {"engine/settings/layers.py", "app/settings_dialog.py"}


def _strings_in_the_code() -> set[str]:
    """Every string literal in the application, outside the two declaring files.

    Parsed rather than grepped: a key inside a comment explaining why it was
    dropped would satisfy a grep and satisfy nobody else.
    """
    found: set[str] = set()
    for path in SOURCE.rglob("*.py"):
        if str(path.relative_to(SOURCE)).replace("\\", "/") in DECLARING:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.add(node.value)
    return found


def test_every_offered_setting_has_a_consumer():
    offered = [key for _title, _icon, _description, keys in GROUPS for key in keys]
    read = _strings_in_the_code()
    unread = sorted(key for key in offered if key not in read)
    assert not unread, f"offered in Preferences and read by nothing: {unread}"


def test_every_default_has_a_consumer():
    """The layout keys are read too, even though the dialog does not offer them."""
    read = _strings_in_the_code()
    unread = sorted(key for key in DEFAULTS if key not in read)
    assert not unread, f"a default nothing reads is dead configuration: {unread}"
