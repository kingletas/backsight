"""Reading a real test run, including what a failing assertion evaluated to.

The stream in `fixtures/tests/run-with-a-failure.jsonl` is genuine output from
`tofu test -json` against the workspace beside it.
"""

from pathlib import Path

import pytest

from backsight.engine.tests.results import Status, parse

ROOT = Path(__file__).resolve().parents[2]
STREAM = (ROOT / "fixtures" / "tests" / "run-with-a-failure.jsonl").read_text()


@pytest.fixture(scope="module")
def results():
    return parse(STREAM)


def test_the_tree_is_built_before_anything_has_run(results):
    """`test_abstract` names every run up front, so the shape shows at once."""
    assert [f.path for f in results.files] == ["tests/nodes.tftest.hcl"]
    names = [run.name for run in results.all_runs()]
    assert names == ["creates_the_right_number", "names_are_wrong_on_purpose"]


def test_each_run_carries_its_own_result(results):
    file = results.file("tests/nodes.tftest.hcl")
    assert file.run("creates_the_right_number").status is Status.PASSED
    assert file.run("names_are_wrong_on_purpose").status is Status.FAILED
    assert file.status is Status.FAILED


def test_a_failure_shows_what_the_expressions_actually_were(results):
    """FR-TST-03, and the single behaviour the design says decides adoption.

    The engine's JSON carries it; only the human-readable output does not.
    """
    failed = results.file("tests/nodes.tftest.hcl").run("names_are_wrong_on_purpose")
    assert failed.failures
    failure = failed.failures[0]
    assert failure.has_evidence
    assert str(failure.values[0]) == "terraform_data.nodes is tuple with 3 elements"


def test_a_failure_carries_the_condition_and_where_to_find_it(results):
    failure = results.file("tests/nodes.tftest.hcl").run("names_are_wrong_on_purpose").failures[0]
    assert failure.condition == "condition     = length(terraform_data.nodes) == 5"
    assert failure.path == "tests/nodes.tftest.hcl"
    assert failure.line == 14
    assert failure.detail == "expected five nodes"


def test_a_passing_run_carries_no_failure(results):
    assert results.file("tests/nodes.tftest.hcl").run("creates_the_right_number").failures == []


def test_the_totals_come_from_the_engine(results):
    assert (results.passed, results.failed, results.errored, results.skipped) == (1, 1, 0, 0)
    assert results.status is Status.FAILED
    assert results.total == 2


def test_the_summary_says_only_what_happened(results):
    """Never `0 errored`. An absence is not a measurement."""
    assert results.summary() == "1 passed · 1 failed"


def test_a_clean_run_says_only_that():
    stream = '{"type":"test_summary","test_summary":{"status":"pass","passed":4,"failed":0}}'
    assert parse(stream).summary() == "4 passed"


def test_an_unfamiliar_message_type_is_ignored_rather_than_refused():
    """The engine adds message types between versions."""
    stream = (
        '{"type":"something_new","whatever":{}}\n'
        '{"type":"test_summary","test_summary":{"status":"pass","passed":1}}'
    )
    assert parse(stream).passed == 1


def test_a_line_that_is_not_json_is_skipped():
    stream = "Initializing modules...\n" + STREAM
    assert parse(stream).total == 2


def test_only_errors_become_failures():
    stream = (
        '{"type":"diagnostic","diagnostic":{"severity":"warning","summary":"deprecated",'
        '"range":{"filename":"a.tftest.hcl","start":{"line":1}}}}'
    )
    assert parse(stream).all_runs() == []
