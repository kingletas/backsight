"""The exposure corpus, and an honest account of what it can establish.

Every case carries a real plan captured from the engine. What it does **not**
carry is independent verification: each answer is meant to be confirmed by a human,
and `verified_by` is null in every case because that has not happened.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "fixtures" / "exposure"


def cases():
    return sorted(d for d in CORPUS.iterdir() if (d / "case.json").is_file())


@pytest.fixture(params=cases(), ids=lambda d: d.name)
def case(request):
    return request.param


def test_every_case_carries_a_real_plan(case):
    """Captured from the engine, not written by hand."""
    plan = json.loads((case / "plan.json").read_text())
    assert plan["format_version"]
    assert plan["terraform_version"]
    assert plan["planned_values"]["root_module"]["resources"]


def test_every_case_states_what_it_expects(case):
    spec = json.loads((case / "case.json").read_text())
    assert spec["description"]
    assert spec["expects"]
    for expectation in spec["expects"]:
        assert expectation["resource"]
        assert expectation["why"], "an expected answer with no reasoning is not reviewable"
        assert expectation["exposed"] in (True, False, None)


def test_no_answer_here_has_been_independently_verified(case):
    """Recorded rather than glossed over.

    Every expected answer is meant to be confirmed by a human and recorded as
    such. Until that happens this file asserts the opposite, so the gap cannot
    quietly become an assumption that it was done.
    """
    spec = json.loads((case / "case.json").read_text())
    assert spec["verified_by"] is None


def test_the_corpus_covers_both_answers_and_the_undecidable_one():
    answers = set()
    for directory in cases():
        for expectation in json.loads((directory / "case.json").read_text())["expects"]:
            answers.add(expectation["exposed"])
    assert answers == {True, False, None}
