"""The last screen before production changes, and what it is allowed to say.

Plate 06 and FR-SEC-05. This is the one moment where friction is the feature, so
everything destructive is stated in plain words before the button is reachable —
including in the button's own label, which is the last warning anybody reads.

FR-ST-03: only a plan artifact that was produced and reviewed may be applied.
The artifact is fingerprinted at review and again at apply, and a difference is
a refusal rather than a re-plan. Silently planning again between review and
apply would mean the thing approved is not the thing that runs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from backsight.engine.plan.model import Action, Plan

# Enough of a digest to be unmistakable in a log and short enough to read out.
DIGEST_LENGTH = 12


@dataclass(frozen=True)
class Target:
    """Where an apply would land, as far as anything currently knows.

    Every field is optional and none is guessed. An unknown account is shown as
    unknown; inventing a plausible one is how somebody applies to the wrong
    place while reading a screen that told them otherwise.
    """

    account: str | None = None
    region: str | None = None
    role: str | None = None
    identity: str | None = None
    expires_at: datetime | None = None

    @property
    def is_known(self) -> bool:
        return bool(self.account and self.region)

    def minutes_left(self, now: datetime | None = None) -> int | None:
        if self.expires_at is None:
            return None
        moment = now or datetime.now(UTC)
        return max(0, int((self.expires_at - moment).total_seconds() // 60))


@dataclass(frozen=True)
class Confirmation:
    """Everything the last screen has to say, worked out in one place."""

    plan: Plan
    artifact: Path
    digest: str
    target: Target
    destroyed: tuple[str, ...] = ()
    replaced: tuple[str, ...] = ()

    @property
    def destroy_count(self) -> int:
        """Objects that will cease to exist, replacements included."""
        return len(self.destroyed) + len(self.replaced)

    @property
    def button_label(self) -> str:
        """The last warning. It names the destruction rather than hiding it."""
        if self.destroy_count == 0:
            return "Apply"
        return f"Destroy {self.destroy_count} and apply"

    @property
    def is_destructive(self) -> bool:
        return self.destroy_count > 0

    def sentences(self) -> list[str]:
        """What is said above the button, in plain words."""
        said = []
        if self.destroyed:
            said.append(
                f"{len(self.destroyed)} resource"
                f"{'' if len(self.destroyed) == 1 else 's'} will be destroyed."
            )
        if self.replaced:
            said.append(
                f"{len(self.replaced)} resource"
                f"{'' if len(self.replaced) == 1 else 's'} will be destroyed and recreated."
            )
        if not said:
            said.append("Nothing will be destroyed.")
        if not self.target.is_known:
            said.append("The account and region are not known. Sign in before applying.")
        return said

    def reasons(self) -> list[str]:
        """Why each replacement is happening, named attribute by attribute."""
        found = []
        for change in self.plan.changes:
            if change.action is not Action.REPLACE:
                continue
            causes = ", ".join(change.replacing_attributes)
            found.append(
                f"{change.address} — replacement forced by {causes}"
                if causes
                else f"{change.address} — replaced; the plan does not say which attribute"
            )
        return found


def digest_of(artifact: Path) -> str:
    """A fingerprint of the plan file, so a changed plan is a different plan."""
    return hashlib.sha256(Path(artifact).read_bytes()).hexdigest()[:DIGEST_LENGTH]


def confirmation_for(plan: Plan, artifact: Path, target: Target | None = None) -> Confirmation:
    return Confirmation(
        plan=plan,
        artifact=Path(artifact),
        digest=digest_of(artifact),
        target=target or Target(),
        destroyed=tuple(c.address for c in plan.changes if c.action is Action.DELETE),
        replaced=tuple(c.address for c in plan.changes if c.action is Action.REPLACE),
    )


def may_apply(confirmation: Confirmation) -> tuple[bool, str]:
    """Whether this plan may still be applied, and why not when it may not."""
    if not confirmation.artifact.is_file():
        return False, "The reviewed plan is gone. Plan again and review it."
    if digest_of(confirmation.artifact) != confirmation.digest:
        # FR-ST-03. Re-planning here would apply something nobody reviewed.
        return False, ("The plan changed after it was reviewed. Review it again before applying.")
    if confirmation.plan.errored:
        return False, "The plan reported errors. Nothing will be applied."
    return True, ""
