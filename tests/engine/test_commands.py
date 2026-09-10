"""Validate and format, read from what the engine really printed."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.plan.commands import UNFORMATTED, formatting, validate
from backsight.engine.runner.process import Capture, Result, RunState, RunTimedOut

CAPTURES = Path(__file__).resolve().parents[2] / "fixtures" / "commands"


def replay(name: str, returncode: int = 0, err: str = ""):
    out = (CAPTURES / name).read_text()

    def run(command, *, cwd=None, stdin="", timeout=0.0, environment=None):
        return Capture(command=tuple(command), returncode=returncode, out=out, err=err, seconds=0.1)

    return run


def test_a_valid_workspace_is_valid(tmp_path: Path):
    answer = validate(tmp_path, run=replay("validate-valid.json"))
    assert answer.valid
    assert answer.problems == []
    assert answer.summary() == "Valid"


def test_an_invalid_one_reports_the_engines_own_words(tmp_path: Path):
    answer = validate(tmp_path, run=replay("validate-invalid.json", returncode=1))
    assert not answer.valid
    assert answer.errors[0].summary == "Reference to undeclared input variable"
    assert "has not been declared" in answer.errors[0].detail


def test_a_problem_carries_the_line_it_is_on(tmp_path: Path):
    """So it can be shown on that line rather than in a wall of output."""
    answer = validate(tmp_path, run=replay("validate-invalid.json", returncode=1))
    assert answer.errors[0].where == "main.tf:2"


def test_the_summary_counts_only_what_is_there(tmp_path: Path):
    answer = validate(tmp_path, run=replay("validate-invalid.json", returncode=1))
    assert answer.summary() == "1 error"


def test_output_that_is_not_json_is_reported_rather_than_crashing(tmp_path: Path):
    """Validate refuses on an uninitialised workspace, in prose on stderr."""

    def run(*_a, **_k):
        return Capture(
            command=("tofu",),
            returncode=1,
            out="",
            err="Error: Missing required provider\n",
            seconds=0.0,
        )

    answer = validate(tmp_path, run=run)
    assert not answer.valid
    assert "Missing required provider" in answer.output


def test_a_hang_is_an_answer_rather_than_an_exception(tmp_path: Path):
    def run(*_a, **_k):
        raise RunTimedOut(
            Result(
                command=("tofu",), state=RunState.TIMED_OUT, returncode=None, output="", seconds=1
            )
        )

    answer = validate(tmp_path, run=run)
    assert not answer.valid
    assert "did not answer" in answer.output


def test_unformatted_files_are_not_a_failure(tmp_path: Path):
    """`fmt -check` exits 3, and treating that as an error calls a tidy-up a break."""
    answer = formatting(tmp_path, run=replay("fmt-needed.out", returncode=UNFORMATTED))
    assert not answer.tidy
    assert answer.files == ("main.tf",)
    assert answer.summary() == "1 file would change"


def test_the_diff_that_would_fix_it_is_kept(tmp_path: Path):
    answer = formatting(tmp_path, run=replay("fmt-needed.out", returncode=UNFORMATTED))
    assert '-    input   =    "x"' in answer.diff
    assert '+  input = "x"' in answer.diff


def test_a_tidy_workspace_says_so(tmp_path: Path):
    def run(*_a, **_k):
        return Capture(command=("tofu",), returncode=0, out="", err="", seconds=0.0)

    answer = formatting(tmp_path, run=run)
    assert answer.tidy
    assert answer.summary() == "Already formatted"


def test_a_real_failure_claims_nothing_about_formatting(tmp_path: Path):
    """Exit 1 is the engine refusing to run, not a verdict about the files."""

    def run(*_a, **_k):
        return Capture(command=("tofu",), returncode=1, out="", err="boom", seconds=0.0)

    assert formatting(tmp_path, run=run).files == ()
