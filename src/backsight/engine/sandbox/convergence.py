"""Applying a configuration against the emulator, to see whether it converges.

FR-SIM-03 to FR-SIM-06. This answers one question — *does this configuration
apply cleanly* — and it is never allowed to answer a different one. A green run
does not predict what will happen in a real account, and every word here is
chosen so nobody can read it that way.

**Coverage is measured, not mapped.** A resource type does not say which service
it belongs to — `aws_db_instance` is `rds` and nothing in the schema says so —
so coverage is what actually converged rather than a name-matching guess that is
right most of the time and silently wrong the rest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from backsight.engine.plan.model import Plan
from backsight.engine.runner import process
from backsight.engine.sandbox.ministack import Sandbox
from backsight.engine.sandbox.override import prepare

APPLY_TIMEOUT = 900.0

# Below this, a run is reported as partial however few resources failed.
DEFAULT_THRESHOLD = 0.80

# What the interface may never say about a sandbox result. FR-SIM-06.
FORBIDDEN_WORDS = ("will happen", "predicts", "guarantees", "production-safe", "proves safe")

# `Error: creating EC2 Instance: ...` and the address it belongs to.
FAILED_ADDRESS = re.compile(r"^\s*with ([a-zA-Z0-9_\.\[\]\"-]+),", re.M)


class Outcome(Enum):
    """How a convergence run ended."""

    CONVERGED = "converged"
    PARTIAL = "partial"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"

    @property
    def is_pass(self) -> bool:
        """Only one of these is a pass, and partial is not it."""
        return self is Outcome.CONVERGED


@dataclass(frozen=True)
class Coverage:
    """How much of the configuration the emulator could actually stand up."""

    attempted: int
    converged: int
    uncovered: tuple[str, ...] = ()

    @property
    def fraction(self) -> float:
        return self.converged / self.attempted if self.attempted else 0.0

    @property
    def percent(self) -> int:
        return round(self.fraction * 100)

    def meets(self, threshold: float = DEFAULT_THRESHOLD) -> bool:
        return self.fraction >= threshold


@dataclass(frozen=True)
class Result:
    """What a convergence run found, and the words to say about it."""

    outcome: Outcome
    coverage: Coverage
    output: str = ""
    emulator_version: str = ""
    reason: str = ""
    uncovered: tuple[str, ...] = field(default=())

    @property
    def headline(self) -> str:
        """Never a bare tick. FR-SIM-05: partial does not get to look like a pass."""
        if self.outcome is Outcome.UNAVAILABLE:
            return "Not run"
        if self.outcome is Outcome.FAILED:
            return "Failed"
        if self.outcome is Outcome.PARTIAL:
            return f"Partial · {self.coverage.percent}% coverage"
        return f"Passed · {self.coverage.percent}% coverage"

    @property
    def disclaimer(self) -> str:
        """Permanent interface text, not onboarding copy. FR-SIM-06.

        People forget onboarding. The screen is there every time.
        """
        return (
            "This checks that your configuration applies cleanly against an "
            "emulator. It does not predict what will happen in your account."
        )


def converge(
    workspace: Path,
    sandbox: Sandbox,
    *,
    services: list[str],
    scratch: Path,
    plan: Plan | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    engine: str = "tofu",
) -> Result:
    """Stands the configuration up against the emulator and reports what happened.

    The user's workspace is copied first, so nothing here can change a file they
    wrote — the override lives only in the copy.
    """
    health = sandbox.health()
    if health is None:
        return Result(
            outcome=Outcome.UNAVAILABLE,
            coverage=Coverage(attempted=0, converged=0),
            reason="The sandbox is not running.",
        )

    directory = prepare(workspace, scratch, endpoint=sandbox.endpoint, services=services)
    sandbox.reset()

    initialised = process.start(
        [engine, "init", "-no-color", "-input=false"], cwd=directory, timeout=APPLY_TIMEOUT
    ).wait(APPLY_TIMEOUT + 30)
    if not initialised.ok:
        return Result(
            outcome=Outcome.FAILED,
            coverage=Coverage(attempted=0, converged=0),
            output=initialised.output,
            emulator_version=health.version,
            reason="The configuration could not be initialised against the sandbox.",
        )

    applied = process.start(
        [engine, "apply", "-no-color", "-input=false", "-auto-approve"],
        cwd=directory,
        timeout=APPLY_TIMEOUT,
    ).wait(APPLY_TIMEOUT + 30)

    attempted = len(plan.effective) if plan is not None else _attempted_from(applied.output)
    failed = tuple(sorted(set(FAILED_ADDRESS.findall(applied.output))))
    converged_count = max(attempted - len(failed), 0)
    coverage = Coverage(attempted=attempted, converged=converged_count, uncovered=failed)

    if applied.ok and not failed:
        outcome = Outcome.CONVERGED if coverage.meets(threshold) else Outcome.PARTIAL
    elif converged_count:
        outcome = Outcome.PARTIAL
    else:
        outcome = Outcome.FAILED

    return Result(
        outcome=outcome,
        coverage=coverage,
        output=applied.output,
        emulator_version=health.version,
        uncovered=failed,
        reason=_reason(outcome, coverage, failed),
    )


def _attempted_from(output: str) -> int:
    """How many resources the apply set out to create, read from its own summary."""
    match = re.search(r"(\d+) added", output)
    if match:
        return int(match.group(1))
    return len(re.findall(r": Creating\.\.\.", output))


def _reason(outcome: Outcome, coverage: Coverage, failed: tuple[str, ...]) -> str:
    if outcome is Outcome.CONVERGED:
        return f"All {coverage.attempted} resources applied cleanly against the emulator."
    if outcome is Outcome.PARTIAL:
        named = ", ".join(failed) if failed else "none named"
        return (
            f"{coverage.converged} of {coverage.attempted} resources applied. "
            f"Not simulated: {named}."
        )
    return "Nothing applied against the emulator."
