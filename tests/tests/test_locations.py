"""Run blocks are found by reading the file, because results do not carry them."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.tests.locations import at, runs

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "tests"
    / "workspace"
    / "tests"
    / "nodes.tftest.hcl"
)
SOURCE = FIXTURE.read_bytes()


def test_every_run_block_is_found_in_file_order():
    found = runs(SOURCE)
    assert [block.name for block in found] == [
        "creates_the_right_number",
        "names_are_wrong_on_purpose",
    ]


def test_lines_are_one_based_to_match_the_engine_and_the_gutter():
    first, second = runs(SOURCE)
    assert (first.line, first.last_line) == (1, 8)
    assert (second.line, second.last_line) == (10, 17)


def test_assertions_are_located_too():
    first, second = runs(SOURCE)
    assert first.assertions == (4,)
    assert second.assertions == (13,)


def test_a_failure_line_finds_the_run_it_belongs_to():
    """The engine reported line 14; the gutter mark belongs to the run around it."""
    block = at(SOURCE, 14)
    assert block is not None
    assert block.name == "names_are_wrong_on_purpose"


def test_a_line_between_blocks_belongs_to_nothing():
    assert at(SOURCE, 9) is None


def test_an_unnamed_run_is_skipped_rather_than_guessed():
    assert runs(b"run {\n  command = apply\n}\n") == []


def test_a_file_with_no_runs_is_empty_not_an_error():
    assert runs(b"variables {\n  size = 3\n}\n") == []


def test_an_empty_file_is_empty():
    assert runs(b"") == []
