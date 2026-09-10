"""The corpus is sound before anything is built against it.

Nothing that generates a `moved` block may be written until the acceptance
test for it exists. This is that test. Every expected verdict here
was produced by a real plan, not by reasoning about one.
"""

import shutil

import pytest
from corpus import cases, plan_after_applying

from backsight.engine.plan.model import Action

pytestmark = pytest.mark.skipif(
    shutil.which("tofu") is None, reason="the engine binary is not installed"
)


def test_the_corpus_covers_what_the_plan_asks_for():
    kinds = {c.kind for c in cases()}
    assert {"rename", "extract", "count-to-for-each", "for-each-key"} <= kinds
    destructive = [c for c in cases() if c.is_destructive]
    assert len(destructive) >= 3, "the plan asks for at least three refusable cases"


def test_every_case_has_both_halves_and_they_differ(case):
    assert case.before.is_dir() and case.after.is_dir()
    # Keyed by path, not name: an extraction has a main.tf in two directories.
    before = {p.relative_to(case.before): p.read_text() for p in case.before.rglob("*.tf")}
    after = {p.relative_to(case.after): p.read_text() for p in case.after.rglob("*.tf")}
    assert before != after, f"{case.name}: the refactor changes nothing"


def test_a_safe_case_names_the_moved_blocks_it_needs(case):
    if case.is_destructive:
        pytest.skip("a destructive case is defined by having none")
    assert case.moved, f"{case.name}: a safe refactor with no moved blocks is not one"
    for source, target in case.moved:
        assert source != target


def test_the_expected_verdict_is_what_a_real_plan_says(case, tmp_path):
    """The assertion the whole milestone rests on.

    A safe refactor plans to nothing. A destructive one destroys something. Both
    are read from the engine here so that no later code can be checked against a
    verdict somebody assumed.
    """
    plan = plan_after_applying(case, tmp_path)
    if case.is_destructive:
        assert plan.is_destructive, (
            f"{case.name} is recorded as destructive and the engine disagrees: {plan.summary()}"
        )
        assert any(c.action in (Action.DELETE, Action.REPLACE) for c in plan.changes)
    else:
        assert not plan.is_destructive, (
            f"{case.name} is recorded as safe and the engine disagrees: {plan.summary()}"
        )
        assert plan.effective == (), f"{case.name} should plan to nothing: {plan.summary()}"
