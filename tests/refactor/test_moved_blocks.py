"""Every corpus case that we generate blocks for produces the expected ones.

The expected blocks in each `case.json` are not opinions: the corpus test proved
each set produces a plan that destroys nothing. This checks the generators emit
exactly those.
"""

import pytest
from corpus import cases

from backsight.engine.refactor.for_each import Conversion
from backsight.engine.refactor.for_each import pairs as for_each_pairs
from backsight.engine.refactor.rename import Rename, moved_block

RENAME = Rename(resource_type="terraform_data", old_name="api", new_name="api_gateway")


def generated_for(case):
    """What this project can generate for a case, or nothing if it cannot yet."""
    if case.kind == "rename":
        return [(RENAME.old_address, RENAME.new_address)]
    if case.kind == "count-to-for-each":
        return for_each_pairs(Conversion("terraform_data", "n", ("a", "b", "c")))
    return None


@pytest.mark.parametrize("case", [c for c in cases() if not c.is_destructive], ids=lambda c: c.name)
def test_a_safe_case_produces_the_moved_blocks_it_was_verified_with(case):
    generated = generated_for(case)
    if generated is None:
        pytest.skip(f"nothing generates blocks for {case.kind} yet")
    assert generated == [(f, t) for f, t in case.moved]


def test_the_block_text_can_be_read_by_a_person():
    """FR-REF-01: users must be able to read what was written and disagree."""
    written = moved_block(RENAME)
    assert written.strip().startswith("moved {")
    assert "from = terraform_data.api" in written
    assert "to   = terraform_data.api_gateway" in written


def test_extract_to_module_is_not_generated_yet():
    """Recorded rather than assumed. The corpus covers it; nothing emits it.

    FR-REF-02 is outside the agreed MVP, and the case exists so the gate is
    exercised against it.
    """
    case = next(c for c in cases() if c.name == "extract-to-module")
    assert generated_for(case) is None
    assert len(case.moved) == 2
