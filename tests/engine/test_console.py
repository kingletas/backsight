"""The console reads captured output from a real engine, never invented shapes."""

from __future__ import annotations

from pathlib import Path

import pytest

from backsight.engine.console import evaluation as console
from backsight.engine.runner.process import Capture, Result, RunState, RunTimedOut

CAPTURES = Path(__file__).resolve().parents[2] / "fixtures" / "console"


def recorded(name: str):
    """Replays one captured run, so a test never needs the engine installed."""
    out = (CAPTURES / f"{name}.out").read_text()
    err = (CAPTURES / f"{name}.err").read_text()

    def run(command, *, cwd=None, stdin="", timeout=0.0, environment=None):
        return Capture(
            command=tuple(command),
            returncode=0 if not err.strip() else 1,
            out=out,
            err=err,
            seconds=0.047,
        )

    return run


def test_a_literal_comes_back_as_its_value(tmp_path: Path) -> None:
    answer = console.evaluate(tmp_path, "1 + 1", run=recorded("literal"))
    assert answer.ok
    assert answer.value == "2"


def test_a_list_keeps_the_engines_own_layout(tmp_path: Path) -> None:
    answer = console.evaluate(tmp_path, '[for n in ["a","b"]: upper(n)]', run=recorded("list"))
    assert answer.ok
    assert answer.value.splitlines()[0] == "["
    assert '"A",' in answer.value


def test_an_object_keeps_its_keys(tmp_path: Path) -> None:
    answer = console.evaluate(tmp_path, "{ a = 1 }", run=recorded("object"))
    assert answer.ok
    assert '"a" = 1' in answer.value


def test_an_unapplied_resource_says_so_rather_than_looking_wrong(tmp_path: Path) -> None:
    answer = console.evaluate(tmp_path, "terraform_data.api", run=recorded("unapplied"))
    assert answer.ok
    assert answer.unapplied


def test_an_undeclared_variable_reports_the_engines_own_summary(tmp_path: Path) -> None:
    answer = console.evaluate(tmp_path, "var.nope", run=recorded("undeclared"))
    assert not answer.ok
    assert answer.failure is not None
    assert answer.failure.summary == "Reference to undeclared input variable"
    assert "has not been declared" in answer.failure.detail


def test_the_meaningless_location_is_not_repeated_back(tmp_path: Path) -> None:
    """Every console error is line 1 of what the person just typed."""
    answer = console.evaluate(tmp_path, "var.nope", run=recorded("undeclared"))
    assert answer.failure is not None
    assert "console-input" not in answer.failure.display
    assert "source code not available" not in answer.failure.display


def test_a_bad_operand_is_reported_as_the_engine_worded_it(tmp_path: Path) -> None:
    answer = console.evaluate(tmp_path, '"a" + 1', run=recorded("operand"))
    assert answer.failure is not None
    assert answer.failure.summary == "Invalid operand"
    assert "a number is required" in answer.failure.detail


def test_an_empty_expression_never_reaches_a_process(tmp_path: Path) -> None:
    def refuse(*_args, **_kwargs):
        raise AssertionError("no process should start for an empty expression")

    answer = console.evaluate(tmp_path, "   ", run=refuse)
    assert not answer.ok
    assert answer.failure is not None
    assert answer.failure.summary == "Nothing to evaluate"


def test_a_sensitive_value_is_recognised_as_withheld_not_missing(tmp_path: Path) -> None:
    def run(*_args, **_kwargs):
        return Capture(
            command=("tofu",), returncode=0, out="(sensitive value)\n", err="", seconds=0.0
        )

    answer = console.evaluate(tmp_path, "var.token", run=run)
    assert answer.ok
    assert answer.redacted


def test_a_hang_is_reported_as_a_hang(tmp_path: Path) -> None:
    def run(*_args, **_kwargs):
        raise RunTimedOut(
            Result(
                command=("tofu",),
                state=RunState.TIMED_OUT,
                returncode=None,
                output="",
                seconds=30.0,
            )
        )

    answer = console.evaluate(tmp_path, "1 + 1", run=run, seconds=30.0)
    assert not answer.ok
    assert answer.failure is not None
    assert "did not answer" in answer.failure.summary


@pytest.mark.parametrize("name", ["literal", "list", "object", "unapplied"])
def test_every_captured_success_produces_a_value(tmp_path: Path, name: str) -> None:
    answer = console.evaluate(tmp_path, "expression", run=recorded(name))
    assert answer.ok
    assert answer.value
