"""Running a corpus case against a real engine.

The expected verdict in each `case.json` is not allowed to be an opinion. It is
checked by applying the `before` files, planning the `after` files against the
state that produced, and reading what the engine says.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from backsight.engine.plan.execution import speculative
from backsight.engine.plan.model import Plan
from backsight.engine.runner import process

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "fixtures" / "refactor"


@dataclass(frozen=True)
class Case:
    """One refactor, its expected output, and what a plan should say about it."""

    name: str
    description: str
    kind: str
    expect: str
    moved: tuple[tuple[str, str], ...]
    path: Path

    @property
    def before(self) -> Path:
        return self.path / "before"

    @property
    def after(self) -> Path:
        return self.path / "after"

    @property
    def is_destructive(self) -> bool:
        return self.expect == "destructive"


def cases() -> list[Case]:
    found = []
    for directory in sorted(CORPUS.iterdir()):
        if not (directory / "case.json").is_file():
            continue
        spec = json.loads((directory / "case.json").read_text(encoding="utf-8"))
        found.append(
            Case(
                name=directory.name,
                description=spec["description"],
                kind=spec["kind"],
                expect=spec["expect"],
                moved=tuple((m["from"], m["to"]) for m in spec.get("moved", [])),
                path=directory,
            )
        )
    return found


def _init(case: Case, workspace: Path) -> None:
    result = process.start(["tofu", "init", "-no-color", "-input=false"], cwd=workspace).wait(180)
    assert result.ok, f"{case.name}: init failed\n{result.output}"


def plan_after_applying(case: Case, workspace: Path) -> Plan:
    """Applies `before`, replaces the files with `after`, and plans.

    This is the only way the expected verdict can be trusted: it is read from
    the engine rather than written down by whoever added the case.
    """
    shutil.copytree(case.before, workspace, dirs_exist_ok=True)
    _init(case, workspace)
    applied = process.start(
        ["tofu", "apply", "-no-color", "-input=false", "-auto-approve"], cwd=workspace
    ).wait(180)
    assert applied.ok, f"{case.name}: the before state would not apply\n{applied.output}"

    for path in workspace.rglob("*.tf"):
        path.unlink()
    shutil.copytree(case.after, workspace, dirs_exist_ok=True)
    # A refactor that creates a module adds one the engine has not installed, so
    # the second init is not a duplicate of the first.
    _init(case, workspace)

    outcome = speculative(workspace)
    assert outcome.ok, f"{case.name}: the after configuration would not plan\n{outcome.output}"
    return outcome.plan
