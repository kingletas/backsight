"""The matrix is a claim about the application, and this is what checks it.

**Adding an engine command without testing it fails the build.** The discovery
walks the package and reports every argument list handed to the engine; the
matrix says what each one is tested with. If the two disagree, one of them is
out of date and this says which.

These are the only tests here that need no emulator: they are about the
application's own source.
"""

from __future__ import annotations

import pytest

from backsight.engine.runner.invocations import commands, found_in
from tests.integration.matrix import MATRIX, NOT_RUN, covered


def test_every_command_the_application_runs_has_a_row():
    """The direction that matters. A command with no row is a command nobody
    has tested against the emulator, and it would be invisible."""
    missing = sorted(set(commands()) - covered())
    assert missing == [], f"engine commands with no row in the matrix: {missing}"


def test_no_row_describes_a_command_the_application_does_not_run():
    """The other direction, which is how a matrix comes to describe a product
    somebody imagined rather than the one that exists."""
    invented = sorted(covered() - set(commands()))
    assert invented == [], f"rows for commands nothing runs: {invented}"


def test_every_row_says_what_verifies_it():
    """A row with no verification is a row saying a command was run."""
    for row in MATRIX:
        assert row.expects.strip(), row.command
        assert row.verified_by.strip(), row.command
        assert row.tests, f"{row.command} names no test"


def test_every_named_test_exists():
    """A matrix pointing at tests that are not there has gone back to being a
    document about intentions."""
    from pathlib import Path

    here = Path(__file__).parent
    said = "\n".join(path.read_text(encoding="utf-8") for path in here.glob("test_*.py"))
    missing = [
        f"{row.command}: {name}"
        for row in MATRIX
        for name in row.tests
        if f"def test_{name}(" not in said
    ]
    assert missing == [], missing


def test_what_is_not_run_is_named_rather_than_left_out():
    """A reader comparing this against Terraform's own command list needs to
    know that `destroy`, `output`, `state` and `workspace` are absent because
    the application does not run them — not because nobody got round to it."""
    for command, why in NOT_RUN.items():
        assert command not in commands(), f"{command} is run after all"
        assert len(why) > 20, f"{command} is dismissed rather than explained"


@pytest.mark.parametrize("one", found_in(), ids=lambda one: one.where)
def test_every_invocation_belongs_to_a_row(one):
    """Per invocation rather than per command, because two call sites of one
    command can pass different arguments — and `plan` does: a speculative plan
    and a refresh-only plan are different things."""
    assert one.command in covered(), f"{one} at {one.where} is in no row"
