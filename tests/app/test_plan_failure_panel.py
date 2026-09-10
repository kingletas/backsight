"""One error, said once — and the engine's own words never thrown away."""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from backsight.app.plan_panel import PlanPanel  # noqa: E402
from backsight.engine.plan.diagnostics import errors  # noqa: E402

Adw.init()

CAPTURES = Path(__file__).resolve().parents[2] / "fixtures" / "plan-failures"
QUOTED = 'variable "tags" {\n  type = "map"\n}\n'


def captured(name: str) -> str:
    return (CAPTURES / f"{name}.out").read_text(encoding="utf-8")


def walk(widget):
    """Every descendant. An unexpanded expander keeps its child off the sibling
    chain, so it is followed by hand — the text is there either way."""
    if isinstance(widget, Gtk.Expander) and widget.get_child() is not None:
        yield widget.get_child()
        yield from walk(widget.get_child())
    child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
    while child is not None:
        yield child
        yield from walk(child)
        child = child.get_next_sibling()


def labels(panel) -> list[str]:
    return [
        w.get_label()
        for w in walk(panel)
        if isinstance(w, Gtk.Label) and w.get_label() and w.get_visible()
    ]


def buttons(panel) -> list[str]:
    return [w.get_label() for w in walk(panel) if isinstance(w, Gtk.Button) and w.get_label()]


def failed(name: str, **kwargs) -> PlanPanel:
    panel = PlanPanel()
    found = errors(captured(name))
    panel.failed("The plan failed", found=found, **kwargs)
    return panel


def test_there_is_no_plan_failed_heading():
    """The blocks below say what failed; a heading is the same error twice."""
    assert "Plan failed" not in labels(failed("quoted-type-constraint"))


def test_a_failure_is_cleared_by_going_back_to_waiting():
    """A heading reading "Plan" over an empty box says nothing the tab above it
    has not already said, so the empty state says what is true instead."""
    panel = failed("quoted-type-constraint")
    panel.waiting("Save to plan")
    said = labels(panel)
    assert "No plan yet" in said
    assert "Save to plan" in said
    assert "Type constraint is quoted" not in said


def test_the_title_is_the_rewritten_one():
    said = labels(failed("quoted-type-constraint", source={"main.tf": QUOTED}))
    assert "Type constraint is quoted" in said
    assert "Invalid quoted type constraints" not in said


def test_the_engines_own_words_are_still_there_verbatim():
    """A translation nobody can check is just a different opacity."""
    panel = failed("quoted-type-constraint", source={"main.tf": QUOTED})
    said = "\n".join(labels(panel))
    assert "Invalid quoted type constraints" in said
    assert "0.11" in said


def test_the_raw_output_starts_collapsed():
    panel = failed("quoted-type-constraint")
    found = [w for w in walk(panel) if isinstance(w, Gtk.Expander)]
    assert found and not any(w.get_expanded() for w in found)


def test_the_location_is_offered_as_somewhere_to_go():
    seen: list[tuple[str, int]] = []
    panel = failed("quoted-type-constraint", on_open=lambda p, n: seen.append((p, n)))
    where = [w for w in walk(panel) if isinstance(w, Gtk.Button) and w.get_label() == "main.tf:2"]
    assert where
    where[0].emit("clicked")
    assert seen == [("main.tf", 2)]


def test_there_is_nowhere_to_go_when_nothing_can_open_it():
    panel = failed("quoted-type-constraint")
    assert "Go to line" not in buttons(panel)


def test_a_deterministic_fix_is_offered_with_the_edit_shown_first():
    panel = failed(
        "quoted-type-constraint",
        source={"main.tf": QUOTED},
        on_open=lambda *_: None,
        on_fix=lambda *_: None,
    )
    assert "Fix and re-plan" in buttons(panel)
    said = labels(panel)
    assert '− type = "map"' in said
    assert "+ type = map(string)" in said


def test_no_fix_is_offered_where_the_value_is_the_users_to_choose():
    panel = failed(
        "missing-required-argument",
        source={"main.tf": 'output "name" {\n}\n'},
        on_open=lambda *_: None,
        on_fix=lambda *_: None,
    )
    assert "Fix and re-plan" not in buttons(panel)


def test_the_fix_hands_back_what_it_would_change():
    handed: list = []
    panel = failed(
        "quoted-type-constraint",
        source={"main.tf": QUOTED},
        on_open=lambda *_: None,
        on_fix=lambda diagnostic, repair: handed.append((diagnostic, repair)),
    )
    fix = [
        w for w in walk(panel) if isinstance(w, Gtk.Button) and w.get_label() == "Fix and re-plan"
    ]
    fix[0].emit("clicked")
    assert handed[0][1].after == "  type = map(string)"
