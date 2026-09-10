"""The console panel shows the answer, and says why a value is missing."""

from __future__ import annotations

import pytest

from backsight.engine.console.evaluation import Evaluation, Failure

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from backsight.app.console_panel import NOT_YET, WITHHELD, ConsolePanel  # noqa: E402


def labels(widget) -> list[str]:
    found: list[str] = []
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Label):
            found.append(child.get_label())
        found.extend(labels(child))
        child = child.get_next_sibling()
    return found


def test_an_answer_reaches_the_screen() -> None:
    panel = ConsolePanel()
    panel.show(Evaluation(expression="1 + 1", value="2"))
    shown = labels(panel)
    assert "› 1 + 1" in shown
    assert "2" in shown


def test_a_failure_shows_the_engines_summary_and_body() -> None:
    panel = ConsolePanel()
    panel.show(
        Evaluation(
            expression="var.nope",
            failure=Failure(summary="Reference to undeclared input variable", detail="Declare it."),
        )
    )
    shown = labels(panel)
    assert "Reference to undeclared input variable" in shown
    assert "Declare it." in shown


def test_a_withheld_value_says_it_was_withheld() -> None:
    """A redaction and an absence look identical without this sentence."""
    panel = ConsolePanel()
    panel.show(Evaluation(expression="var.token", value="(sensitive value)"))
    assert WITHHELD in labels(panel)


def test_an_unapplied_value_says_why_it_is_not_there() -> None:
    panel = ConsolePanel()
    panel.show(Evaluation(expression="terraform_data.api", value="(known after apply)"))
    assert NOT_YET in labels(panel)


def test_submitting_sends_the_expression_and_clears_the_entry() -> None:
    asked: list[str] = []
    panel = ConsolePanel(on_evaluate=asked.append)
    panel.entry.set_text("length([1])")
    panel.submit()
    assert asked == ["length([1])"]
    assert panel.entry.get_text() == ""
    assert panel.history == ["length([1])"]


def test_an_empty_entry_asks_nothing() -> None:
    asked: list[str] = []
    panel = ConsolePanel(on_evaluate=asked.append)
    panel.entry.set_text("   ")
    panel.submit()
    assert asked == []


def test_clearing_forgets_the_session() -> None:
    panel = ConsolePanel()
    panel.show(Evaluation(expression="1 + 1", value="2"))
    panel.clear()
    assert "2" not in labels(panel)
    assert panel.history == []
