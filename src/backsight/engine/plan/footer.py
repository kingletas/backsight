"""What the footer offers, which is whatever the person should do next.

There was one button, Apply, and it spent most of its life greyed out with a
sentence beside it explaining why. A permanently dead primary action teaches
people that the footer is scenery, and then the one moment it matters — an
apply that will destroy something — it is scenery.

So Apply is not disabled elsewhere. **It is absent**, and the footer carries the
action that is actually available: run the plan, cancel it, fix it, review it,
apply it. When there is nothing to do there is no footer, rather than an empty
bar holding the space.

This decides; `app/apply_gate.py` draws it. The decision is here because it is
the part worth testing, and because a footer that disagrees with the status bar
is the contradiction the whole panel exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Situation:
    """Everything the footer's decision depends on, and nothing else."""

    plan: object | None = None
    running: bool = False
    elapsed: float = 0.0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    changes: int = 0
    irreversible: int = 0
    environment: str = ""
    fixable: bool = False
    reviewed: bool = False
    policy: str = ""
    # A blocker with no action behind it. Applying is impossible and no button
    # here can change that, so the footer offers the reading instead and names
    # the reason rather than asking somebody to go and find it.
    blocked: str = ""
    # How long ago this plan was taken, in seconds. Infrastructure moves, and a
    # plan is a description of a difference at one moment — so the last thing
    # read before an irreversible press should say when that moment was.
    plan_age: float = 0.0
    # Whether this workspace keeps its state on one machine. Not a blocker —
    # applying works — but it is what applying **costs**, and the footer is the
    # last thing read before somebody presses it. It was a banner on open,
    # which is hours before it means anything and is where it got dismissed.
    local_state: bool = False


@dataclass(frozen=True)
class Footer:
    """One primary action, and one specific sentence about why."""

    action: str
    command: str
    detail: str = ""
    irreversible: int = 0
    confirm: str = ""

    @property
    def wants_confirmation(self) -> bool:
        return bool(self.confirm)


def footer(now: Situation) -> Footer | None:
    """The footer, or None where there is nothing for one to hold."""
    if now.running:
        return Footer("Cancel", "cancel-plan", f"Planning… {now.elapsed:.0f}s")

    if now.plan is None:
        if now.errors:
            return Footer(
                "Fix and re-plan" if now.fixable else "Re-plan",
                "fix-and-replan" if now.fixable else "plan-now",
                _where(now.errors),
            )
        return Footer("Run plan", "plan-now")

    if now.policy:
        return Footer("Request exception", "policy-exception", f"{now.policy} blocks apply")

    if now.changes == 0:
        # Nothing to do, so nothing to offer. An empty bar holding the space is
        # the footer claiming there is a decision here.
        return None

    if now.blocked:
        return Footer(f"Review {now.changes} change{_s(now.changes)}", "open-changes", now.blocked)

    if now.warnings and not now.reviewed:
        return Footer(
            f"Review {now.changes} change{_s(now.changes)}",
            "open-changes",
            _warned(now.warnings),
        )

    said = [f"{now.irreversible} irreversible"] if now.irreversible else []
    stale = _how_old(now.plan_age)
    if stale:
        said.append(stale)
    if now.local_state:
        # At the moment it means something, which is the only moment it does.
        said.append("state is on this machine only")
    return Footer(
        f"Apply {now.changes} change{_s(now.changes)}",
        "apply",
        " · ".join(said),
        irreversible=now.irreversible,
        confirm=now.environment if now.irreversible and now.environment else "",
    )


# A plan taken seconds ago is the normal case, and saying so on every apply is
# a line nobody reads by the fifth time. It speaks when the answer has stopped
# being obvious.
FRESH_FOR = 120.0


def _how_old(seconds: float) -> str:
    """How long ago the plan was taken, and nothing while it is still fresh."""
    if seconds < FRESH_FOR:
        return ""
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"planned {minutes} minutes ago"
    hours = minutes // 60
    return f"planned {hours} hour{_s(hours)} ago"


def _s(count: int) -> str:
    return "" if count == 1 else "s"


def _where(errors: list) -> str:
    """How many, and where — never a count on its own."""
    files = {getattr(error, "path", "") for error in errors if getattr(error, "path", "")}
    said = f"{len(errors)} error{_s(len(errors))}"
    if len(files) == 1:
        return f"{said} in {files.pop()}"
    if files:
        return f"{said} in {len(files)} files"
    return said


def _warned(warnings: list) -> str:
    return f"{len(warnings)} warning{_s(len(warnings))}, none blocking"
