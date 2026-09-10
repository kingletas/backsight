"""Formatting one buffer, against the real `fmt -`."""

from __future__ import annotations

from pathlib import Path

import pytest

from backsight.engine.plan.commands import format_text

CAPTURED = Path(__file__).resolve().parents[2] / "fixtures" / "fmt"
UNFORMATTED = (CAPTURED / "unformatted.tf").read_text()
FORMATTED = (CAPTURED / "formatted.tf").read_text()
BROKEN = (CAPTURED / "broken.tf").read_text()
COMPLAINT = (CAPTURED / "broken.out").read_text()


def pretend(out: str = "", err: str = "", code: int = 0):
    """Stands in for the engine, with output it really produced."""
    from backsight.engine.runner.process import Capture

    def run(_command, *, cwd=None, stdin="", timeout=0.0):
        return Capture(command=tuple(_command), out=out, err=err, returncode=code, seconds=0.0)

    return run


def test_it_hands_back_the_formatted_text():
    said = format_text(UNFORMATTED, run=pretend(out=FORMATTED))
    assert said.ok
    assert said.text == FORMATTED


def test_text_that_is_already_formatted_changes_nothing():
    """So a save cannot rewrite the buffer and move the caret for no reason."""
    said = format_text(FORMATTED, run=pretend(out=FORMATTED))
    assert said.ok
    assert not said.changed_anything


def test_a_file_that_will_not_parse_is_left_exactly_as_it_is():
    said = format_text(BROKEN, run=pretend(err=COMPLAINT, code=1))
    assert not said.ok
    assert not said.changed_anything
    assert "Unclosed configuration block" in said.complaint


def test_a_failure_with_nothing_said_still_says_something():
    said = format_text(BROKEN, run=pretend(code=1))
    assert said.complaint == "Formatting failed"


def test_a_run_that_hangs_is_not_a_formatted_file():
    from backsight.engine.runner.process import Result, RunState, RunTimedOut

    def hang(command, **_k):
        raise RunTimedOut(
            Result(
                command=tuple(command),
                state=RunState.TIMED_OUT,
                returncode=None,
                output="",
                seconds=9.9,
            )
        )

    said = format_text(UNFORMATTED, run=hang)
    assert not said.ok
    assert not said.changed_anything


@pytest.mark.sandbox
def test_against_the_real_engine():
    said = format_text(UNFORMATTED)
    assert said.ok
    assert said.text == FORMATTED
