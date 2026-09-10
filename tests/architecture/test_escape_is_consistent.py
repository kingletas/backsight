"""Escape behaves the same way everywhere, and this is what keeps it that way.

Three rules, each of which was broken somewhere before it was written down:

1. **Every surface that opens on top of the window takes Escape at the capture
   phase.** A controller at the bubble phase is the *last* thing to see the key,
   after every widget inside — and `Gtk.SearchEntry`, `Gtk.Text` with a
   selection and an open popover all consume it. The command palette listened
   for Escape from the day it was written and Escape did nothing.
2. **Every question names a close response**, so Escape has an answer to give.
   A dialog without one either ignores the key or picks the first response,
   and which of those it does is not something to leave to the toolkit.
3. **That answer is never the destructive one.** Escaping an irreversible
   choice is not the same as making it, and the two readings of the press —
   *no* and *never mind* — are the same keystroke.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "src" / "backsight" / "app"


def modules() -> list[Path]:
    return sorted(APP.rglob("*.py"))


def calls(tree: ast.AST, attribute: str) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == attribute
    ]


def enclosing(tree: ast.AST, node: ast.AST) -> ast.AST | None:
    """The function a call sits in, which is where its neighbours are."""
    for candidate in ast.walk(tree):
        if not isinstance(candidate, ast.FunctionDef):
            continue
        if any(one is node for one in ast.walk(candidate)):
            return candidate
    return None


def dialogs() -> list[tuple[Path, ast.AST, ast.Call]]:
    found = []
    for path in modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in calls(tree, "MessageDialog"):
            found.append((path, tree, call))
    return found


def test_the_application_still_has_questions_to_ask():
    """A rule nothing violates because nothing exists is not a rule."""
    assert len(dialogs()) >= 8


@pytest.mark.parametrize("case", dialogs(), ids=lambda case: f"{case[0].name}:{case[2].lineno}")
def test_every_question_says_what_escape_answers(case):
    path, tree, call = case
    where = enclosing(tree, call)
    assert where is not None, f"{path.name}:{call.lineno} is not inside a function"
    named = calls(where, "set_close_response")
    assert named, (
        f"{path.name}:{call.lineno} asks a question with no close response, so "
        "Escape either does nothing or picks whichever answer came first"
    )


@pytest.mark.parametrize("case", dialogs(), ids=lambda case: f"{case[0].name}:{case[2].lineno}")
def test_escape_never_answers_with_the_destructive_one(case):
    path, tree, call = case
    where = enclosing(tree, call)
    destructive = {
        node.args[0].value
        for node in calls(where, "set_response_appearance")
        if node.args
        and isinstance(node.args[0], ast.Constant)
        and "DESTRUCTIVE" in ast.dump(node.args[1])
    }
    for closing in calls(where, "set_close_response"):
        if not closing.args or not isinstance(closing.args[0], ast.Constant):
            continue
        assert closing.args[0].value not in destructive, (
            f"{path.name}:{call.lineno} lets Escape choose the destructive answer"
        )


# --- capture, not bubble ----------------------------------------------------

# Surfaces that open over the window and have to take Escape before their own
# contents can eat it. Listed rather than discovered, because a name here is a
# commitment: adding a modal means adding it to this list.
OVER_THE_WINDOW = ("palette.py", "window.py", "dismissable.py")


@pytest.mark.parametrize("name", OVER_THE_WINDOW)
def test_escape_is_taken_at_the_capture_phase(name: str):
    """Every one of these goes through `escape_closes`, which is the only place
    the phase is set — so there is one thing to get right rather than four."""
    said = (APP / name).read_text(encoding="utf-8")
    assert "escape_closes" in said, f"{name} wires Escape by hand"


# The one other place a key controller takes the capture phase, and why it is
# allowed to. A snippet's fields live *inside* the buffer, so Escape has to
# leave them before anything around the buffer closes — and the window's own
# controller runs first, being the outer widget, so the window asks the editor
# rather than leaving the editor to catch what is left.
INNERMOST = "tab_stops.py"


def test_only_two_places_take_a_key_at_the_capture_phase():
    """A third is a third answer to a question that has one, and the order
    between them is what decides which thing one press closes."""
    found = []
    for path in modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in calls(tree, "set_propagation_phase"):
            where = enclosing(tree, node)
            # A click gesture at capture is a different question — `split.py`
            # uses one so a click into a pane makes it the active one.
            if where is not None and "EventControllerKey" in ast.dump(where):
                found.append(path.name)
    assert sorted(found) == sorted(["dismissable.py", INNERMOST]), found


def test_the_window_leaves_a_snippet_before_it_closes_anything_else():
    """One press must not take the drawer and leave you still in a field."""
    said = (APP / "window.py").read_text(encoding="utf-8")
    where = said.index("def _escape_dismissed_something")
    body = said[where : said.index("\n    def ", where + 10)]
    assert body.index("is_live") < body.index("stop_peeking"), (
        "the window closes something outside the buffer before leaving the snippet inside it"
    )


def test_no_surface_refuses_to_be_escaped():
    """The opt-out is unnecessary here, and that is a claim worth checking.

    Every question this application asks points Escape at its harmless answer,
    so there is nothing for a refusal to protect. A surface that takes the key
    away has to justify itself against the two tests above rather than arrive
    quietly.
    """
    for path in sorted(APP.glob("*.py")):
        said = path.read_text(encoding="utf-8")
        assert "set_can_close(False)" not in said, (
            f"{path.name} refuses to be closed — say which question Escape may not answer"
        )
