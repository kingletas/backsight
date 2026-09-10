"""Nothing writes into a committed fixture.

`fixtures/example/a-module-worth-copying.tf` was written into the repository by
something driving the window at a fixture directly rather than at a copy, and
then committed. It declared required variables, so every plan against that
workspace failed afterwards — and the failure looked like a bug in planning.

The whole class is worth a guard, because the symptom appears nowhere near the
cause and a polluted fixture is invisible in a green suite.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=False
    ).stdout


def _dirty() -> set[str]:
    return {
        line
        for line in _git("status", "--porcelain", "--", "fixtures").splitlines()
        if line.strip()
    }


@pytest.fixture(scope="session")
def before_the_suite_ran() -> set[str]:
    """What was already dirty under `fixtures/` when the run started.

    **The guard is about what a test wrote, not about what a person added.** It
    compared against a clean tree, so writing a new fixture made the suite red
    until the fixture was committed — which is a guard telling somebody off for
    doing the thing it exists to make safe.
    """
    return _dirty()


def test_no_fixture_has_been_changed_or_added_underneath_us(before_the_suite_ran):
    """Run after anything that drives a window. A test that copies its
    workspace cannot trip this; one that opens a fixture directly will."""
    stray = sorted(_dirty() - before_the_suite_ran)
    assert stray == [], "something wrote into the fixtures:\n" + "\n".join(stray)


def test_the_example_workspace_is_only_what_it_should_be():
    """It exists to plan offline and show all four kinds of change. Anything
    else in it changes what the first plan somebody sees says."""
    found = sorted(one.name for one in (FIXTURES / "example").iterdir() if one.is_file())
    assert found == ["main.tf", "terraform.tfstate"]


# The workspaces the application plans directly. A module is called with values
# by whoever calls it, so a required variable there is its interface rather than
# a fault — this is only about the ones a plan runs against on their own.
PLANNED_DIRECTLY = ("example", "plannable", "apply-fails", "broken-plan")


def test_a_workspace_that_gets_planned_has_nothing_it_cannot_plan_without():
    """A variable with no default makes every plan against it fail with "no
    value for required variable", which reads as a bug in planning."""
    import re

    for name in PLANNED_DIRECTLY:
        where = FIXTURES / name
        if not where.is_dir():
            continue
        for path in where.glob("*.tf"):
            text = path.read_text(encoding="utf-8")
            for block in re.finditer(r'variable\s+"([^"]+)"\s*\{(.*?)\n\}', text, re.S):
                assert "default" in block.group(2), (
                    f"{path.relative_to(ROOT)} declares {block.group(1)} with no default"
                )
