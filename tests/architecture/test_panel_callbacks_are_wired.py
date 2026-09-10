"""Every callback a panel accepts is passed something by the window.

`TestPanel` took an `on_run` and the window built it as `TestPanel()`. The panel
could run tests, the window could run tests, and nothing joined the two — so the
tests panel was a display with no way to act from it.

This is the same defect as the keymap that installed nothing and the settings
nothing read: the part works, the route does not exist, and no test of either
half can see it.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import get_type_hints

import pytest

ROOT = Path(__file__).resolve().parents[2]
WINDOW = ROOT / "src" / "backsight" / "app" / "window.py"

# A callback the window has no business supplying, with the reason. Anything
# not named here is expected to be wired.
DELIBERATELY_UNWIRED: dict[tuple[str, str], str] = {}


def _how_the_window_builds_them() -> dict[str, set[str]]:
    """Panel class name -> the keyword arguments the window passes it."""
    built: dict[str, set[str]] = {}
    for node in ast.walk(ast.parse(WINDOW.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        if not node.func.id.endswith("Panel"):
            continue
        given = {word.arg for word in node.keywords if word.arg}
        built.setdefault(node.func.id, set()).update(given)
    return built


def test_every_panel_callback_the_window_could_pass_is_passed():
    pytest.importorskip("gi", reason="the toolkit is not installed")
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")

    from backsight.app import window as module

    built = _how_the_window_builds_them()
    missing: list[str] = []
    for name, given in built.items():
        panel = getattr(module, name, None)
        if panel is None:
            continue
        hints = get_type_hints(panel.__init__)
        for argument in inspect.signature(panel.__init__).parameters:
            if argument in ("self", "args", "kwargs"):
                continue
            said = hints.get(argument)
            if said is None or "Callable" not in str(said):
                continue
            if argument in given or (name, argument) in DELIBERATELY_UNWIRED:
                continue
            missing.append(f"{name}({argument}=…) is never passed")
    assert missing == [], "; ".join(missing)
