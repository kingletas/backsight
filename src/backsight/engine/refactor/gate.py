"""Nothing is offered as a finished refactor until a plan says it destroys nothing.

FR-REF-03 and DD-10. The failure mode here is destroyed production
infrastructure, so this refuses rather than warns: a refused refactor costs a
minute, and a wrong one costs a database.

The check is a real plan against the real state, run on a copy of the workspace
so the user's files are untouched whatever the answer turns out to be.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from backsight.engine.plan.execution import speculative
from backsight.engine.plan.model import Action, Plan
from backsight.engine.refactor.edits import Edit, apply_to, group

# Copied into the scratch workspace so the plan runs against the same state and
# the same providers. Without these the plan is about a different workspace.
CARRIED = (".terraform", ".terraform.lock.hcl", "terraform.tfstate")


@dataclass(frozen=True)
class Proposal:
    """A refactor, before anyone has decided whether it may happen."""

    description: str
    edits: list[Edit] = field(default_factory=list)
    appended: dict[Path, str] = field(default_factory=dict)

    def rewrite(self, directory: Path) -> dict[Path, bytes]:
        """What every touched file would contain, relative to the module root."""
        out: dict[Path, bytes] = {}
        for relative, edits in group(self.edits).items():
            out[relative] = apply_to((directory / relative).read_bytes(), edits)
        for relative, text in self.appended.items():
            base = out.get(relative)
            if base is None:
                # A file that is not there yet is one this refactor is creating.
                # Extracting to a module writes new files, and reading them
                # first would be reading something nobody has written.
                found = directory / relative
                base = found.read_bytes() if found.is_file() else b""
            out[relative] = base + text.encode("utf-8")
        return out


@dataclass(frozen=True)
class Verdict:
    """Whether the refactor may be applied, and why not when it may not."""

    accepted: bool
    reason: str
    plan: Plan | None = None
    destroyed: tuple[str, ...] = ()

    @property
    def refused(self) -> bool:
        return not self.accepted


def verify(proposal: Proposal, directory: Path, *, scratch: Path) -> Verdict:
    """Plans the proposed files against real state and reads the answer.

    A plan that will not run is a refusal too. Not knowing whether something is
    destructive is not the same as knowing it is safe.
    """
    workspace = _copy_workspace(directory, scratch)
    for relative, data in proposal.rewrite(directory).items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    outcome = speculative(workspace)
    if outcome.plan is None:
        return Verdict(
            accepted=False,
            reason=(
                "The refactor was not applied: the plan that would prove it safe "
                f"could not run. {outcome.failure or ''}".strip()
            ),
        )

    plan = outcome.plan
    destroyed = tuple(
        change.address
        for change in plan.changes
        if change.action in (Action.DELETE, Action.REPLACE)
    )
    if destroyed:
        return Verdict(
            accepted=False,
            reason=(
                f"The refactor was not applied. A plan says it would destroy "
                f"{len(destroyed)} resource{'' if len(destroyed) == 1 else 's'}: "
                f"{', '.join(destroyed)}."
            ),
            plan=plan,
            destroyed=destroyed,
        )

    if plan.effective:
        # Not destructive, but not nothing either. A rename that also changes
        # something is two operations, and the user asked for one.
        return Verdict(
            accepted=False,
            reason=(
                "The refactor was not applied: it would change infrastructure as "
                f"well as move it — {plan.summary()}."
            ),
            plan=plan,
        )

    return Verdict(
        accepted=True, reason="A plan confirms this moves state and changes nothing.", plan=plan
    )


def apply_refactor(proposal: Proposal, directory: Path, *, scratch: Path) -> Verdict:
    """Verifies, then writes. Never the other way round.

    This is the only sanctioned way to put a refactor on disk. Anything that
    writes the files itself has skipped the gate.
    """
    verdict = verify(proposal, directory, scratch=scratch)
    if verdict.refused:
        return verdict
    for relative, data in proposal.rewrite(directory).items():
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return verdict


def _copy_workspace(directory: Path, scratch: Path) -> Path:
    scratch.mkdir(parents=True, exist_ok=True)
    for path in directory.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(directory)
        if (
            relative.parts
            and relative.parts[0].startswith(".")
            and relative.parts[0] not in CARRIED
        ):
            continue
        target = scratch / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    return scratch
