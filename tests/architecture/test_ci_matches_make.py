"""What CI runs has to exist here, and `make ci` has to be the same thing.

A workflow that invokes a target this repository does not have fails ten minutes
after a push, on somebody else's machine, for a reason that was knowable before
it left.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "check.yml"
MAKEFILE = ROOT / "Makefile"


def make_targets() -> set[str]:
    return set(re.findall(r"(?m)^([a-zA-Z][\w-]*):", MAKEFILE.read_text(encoding="utf-8")))


def workflow_make_calls() -> set[str]:
    spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    called = set()
    for job in spec["jobs"].values():
        for step in job["steps"]:
            for line in (step.get("run") or "").splitlines():
                called.update(re.findall(r"\bmake\s+([a-zA-Z][\w-]*)", line))
    return called


def test_ci_calls_only_targets_that_exist():
    missing = workflow_make_calls() - make_targets()
    assert not missing, f"CI calls make targets this repository does not have: {sorted(missing)}"


def test_every_action_is_pinned_to_a_commit():
    """A tag can be moved by whoever owns the action; a commit cannot."""
    spec = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in spec["jobs"].values():
        for step in job["steps"]:
            uses = step.get("uses")
            if uses and not re.search(r"@[0-9a-f]{40}$", uses):
                raise AssertionError(f"{uses} is not pinned to a commit")


def test_the_gate_is_reachable_from_ci():
    assert "check" in workflow_make_calls(), "CI does not run `make check`"
