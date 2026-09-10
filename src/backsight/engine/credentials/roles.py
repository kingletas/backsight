"""Which profile an operation uses, and why it is not always the same one.

FR-SEC-04. Reading a plan needs to see the account; applying needs to change
it; and the two should not be the same set of permissions when somebody's setup
offers both. A read-only profile for planning means a mis-click during a plan
cannot alter anything, which is a guarantee no amount of care in the interface
can otherwise provide.

Nothing is guessed. If a person has one profile, everything uses it and this
says so plainly rather than inventing a second.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backsight.engine.credentials.profiles import Available, Profile

# Names that conventionally mean read-only. Matched only to *suggest* a pairing
# — never to decide one, because a profile called `readonly` that is not is a
# trap this application must not spring.
READING_NAMES = ("readonly", "read-only", "read", "viewer", "audit")


class Operation(Enum):
    """What is being done, in the terms permissions are granted in."""

    READ = "reading"
    CHANGE = "changing"

    @property
    def label(self) -> str:
        return {
            Operation.READ: "Plan, drift and analysis",
            Operation.CHANGE: "Apply",
        }[self]


@dataclass(frozen=True)
class Choice:
    """Which profile an operation will use, and how that was decided."""

    operation: Operation
    profile: Profile | None
    why: str

    @property
    def is_chosen(self) -> bool:
        return self.profile is not None

    @property
    def summary(self) -> str:
        if self.profile is None:
            return f"{self.operation.label}: nothing to use"
        return f"{self.operation.label}: {self.profile.name}"


@dataclass(frozen=True)
class Pairing:
    """What each operation uses, and whether they differ at all."""

    reading: Choice
    changing: Choice

    @property
    def is_split(self) -> bool:
        """Whether reading and changing use different profiles."""
        if not (self.reading.is_chosen and self.changing.is_chosen):
            return False
        return self.reading.profile.name != self.changing.profile.name

    @property
    def summary(self) -> str:
        if not self.changing.is_chosen:
            return "Nothing to apply with"
        if not self.is_split:
            return f"{self.changing.profile.name} for everything"
        return f"{self.reading.profile.name} to read, {self.changing.profile.name} to apply"


def _looks_read_only(profile: Profile) -> bool:
    said = f"{profile.name} {profile.role}".lower()
    return any(word in said for word in READING_NAMES)


def choose(available: Available, *, preferred: str = "") -> Pairing:
    """Which profile each operation uses.

    A named preference wins outright — somebody who chose is not asked to argue
    with a heuristic. Otherwise: the default profile changes things, and a
    profile that names itself read-only reads. With one profile, both are it,
    and the reason says so rather than implying a split that does not exist.
    """
    chosen = available.named(preferred) if preferred else None
    if chosen is not None:
        return Pairing(
            reading=Choice(Operation.READ, chosen, "you chose it"),
            changing=Choice(Operation.CHANGE, chosen, "you chose it"),
        )

    if not available.profiles:
        why = (
            "credentials are in the environment"
            if available.from_environment
            else "there are no profiles"
        )
        empty = None
        return Pairing(
            reading=Choice(Operation.READ, empty, why),
            changing=Choice(Operation.CHANGE, empty, why),
        )

    changing = available.default or available.profiles[0]
    reading = next(
        (one for one in available.profiles if _looks_read_only(one)),
        changing,
    )
    return Pairing(
        reading=Choice(
            Operation.READ,
            reading,
            "it names itself read-only" if reading is not changing else "the only one there is",
        ),
        changing=Choice(
            Operation.CHANGE,
            changing,
            "it is the default profile" if changing.is_default else "the only one there is",
        ),
    )
