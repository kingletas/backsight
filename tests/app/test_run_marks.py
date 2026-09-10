"""The gutter says how each run last went, and its tooltip says what a click does."""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")

from backsight.app.run_marks import RunMarks  # noqa: E402
from backsight.engine.tests.results import Status, parse  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "fixtures" / "tests" / "workspace" / "tests" / "nodes.tftest.hcl").read_bytes()
RESULTS = parse((ROOT / "fixtures" / "tests" / "run-with-a-failure.jsonl").read_text())


def test_each_run_is_marked_with_its_own_result():
    marks = RunMarks()
    marks.show(SOURCE, RESULTS, Path("tests/nodes.tftest.hcl"))
    first = marks.mark_at(0)
    second = marks.mark_at(9)
    assert first is not None and second is not None
    assert first.status is Status.PASSED
    assert second.status is Status.FAILED


def test_a_run_that_has_not_run_is_pending_not_missing():
    """The shape of the file appears before anything has been run."""
    marks = RunMarks()
    marks.show(SOURCE, None, Path("tests/nodes.tftest.hcl"))
    assert marks.mark_at(0) is not None
    assert marks.mark_at(0).status is Status.PENDING


def test_pass_and_fail_do_not_share_a_shape():
    marks = RunMarks()
    marks.show(SOURCE, RESULTS, Path("tests/nodes.tftest.hcl"))
    assert marks.mark_at(0).shape != marks.mark_at(9).shape


def test_lines_without_a_run_block_carry_no_mark():
    marks = RunMarks()
    marks.show(SOURCE, RESULTS, Path("tests/nodes.tftest.hcl"))
    assert marks.mark_at(4) is None


def test_the_tooltip_says_the_file_will_run_not_the_run():
    """The engine has no per-run filter, so the label must not imply one."""
    marks = RunMarks()
    marks.show(SOURCE, RESULTS, Path("tests/nodes.tftest.hcl"))
    tooltip = marks.mark_at(9).tooltip(Path("tests/nodes.tftest.hcl"), 2)
    assert "names_are_wrong_on_purpose" in tooltip
    assert "Click to run nodes.tftest.hcl again (2 runs)." in tooltip


def test_one_run_is_not_called_runs():
    marks = RunMarks()
    marks.show(SOURCE, RESULTS, Path("a.tftest.hcl"))
    assert "(1 run)." in marks.mark_at(0).tooltip(Path("a.tftest.hcl"), 1)


def test_a_file_with_no_runs_marks_nothing():
    marks = RunMarks()
    marks.show(b"variables {\n  size = 1\n}\n", RESULTS, Path("vars.tftest.hcl"))
    assert marks.mark_at(0) is None


def test_clearing_removes_every_mark():
    marks = RunMarks()
    marks.show(SOURCE, RESULTS, Path("tests/nodes.tftest.hcl"))
    marks.clear()
    assert marks.mark_at(0) is None
