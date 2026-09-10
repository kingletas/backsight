"""Which provider version a workspace actually gets served.

FR-SCH-02. Completing an attribute from a newer provider into a workspace pinned
at an older one is worse than completing nothing: it reads as authoritative and
it is wrong. The lock file is the answer whenever there is one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# `>= 1.2.0`, `~> 5.82`, `!= 3.0.0`, or a bare `5.82.2`. Terraform separates
# several of these with commas and requires all of them to hold.
CONSTRAINT = re.compile(r"^\s*(=|!=|>=|<=|>|<|~>)?\s*([0-9]+(?:\.[0-9]+)*)\s*$")


@dataclass(frozen=True)
class Resolution:
    """Which version will be served, and why that one."""

    provider: str
    version: str | None
    pinned: bool
    reason: str

    @property
    def servable(self) -> bool:
        return self.version is not None


def parse_version(text: str) -> tuple[int, ...]:
    """A version as numbers, so `3.10.0` sorts above `3.9.0` rather than below it."""
    return tuple(int(part) for part in re.findall(r"[0-9]+", text))


def _pad(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    width = max(len(left), len(right))
    return left + (0,) * (width - len(left)), right + (0,) * (width - len(right))


def satisfies(version: str, constraint: str | None) -> bool:
    """Whether a version meets a constraint string, all clauses of it."""
    if not constraint:
        return True
    candidate = parse_version(version)
    for clause in constraint.split(","):
        match = CONSTRAINT.match(clause)
        if match is None:
            # An unreadable constraint is not quietly treated as satisfied. Saying
            # nothing is the safe answer; guessing yes is how the wrong schema
            # gets served.
            return False
        operator, wanted_text = match.group(1) or "=", match.group(2)
        wanted = parse_version(wanted_text)
        if operator == "~>":
            # Pessimistic: the last named part may grow, nothing above it may.
            floor, ceiling_index = wanted, len(wanted) - 1
            left, right = _pad(candidate, floor)
            if left < right:
                return False
            if candidate[:ceiling_index] != floor[:ceiling_index]:
                return False
            continue
        left, right = _pad(candidate, wanted)
        checks = {
            "=": left == right,
            "!=": left != right,
            ">=": left >= right,
            "<=": left <= right,
            ">": left > right,
            "<": left < right,
        }
        if not checks[operator]:
            return False
    return True


def resolve(
    provider_name: str,
    *,
    locked_version: str | None,
    constraint: str | None,
    indexed: list[str],
) -> Resolution:
    """Picks the version to serve for one provider.

    The lock file wins outright when there is one, even if the index does not
    hold it — serving a different version because the right one is missing is the
    failure this whole function exists to prevent.
    """
    available = sorted(indexed, key=parse_version, reverse=True)

    if locked_version:
        if locked_version in available:
            return Resolution(
                provider=provider_name,
                version=locked_version,
                pinned=True,
                reason="pinned by the lock file",
            )
        return Resolution(
            provider=provider_name,
            version=None,
            pinned=True,
            reason=f"{locked_version} is pinned by the lock file and is not indexed",
        )

    matching = [version for version in available if satisfies(version, constraint)]
    if not matching:
        return Resolution(
            provider=provider_name,
            version=None,
            pinned=False,
            reason=(
                f"no indexed version satisfies {constraint}"
                if constraint
                else "no version of this provider is indexed"
            ),
        )
    return Resolution(
        provider=provider_name,
        version=matching[0],
        pinned=False,
        reason=(
            "newest indexed version that satisfies the constraint; "
            "there is no lock file, so this is not what a plan is guaranteed to use"
        ),
    )
