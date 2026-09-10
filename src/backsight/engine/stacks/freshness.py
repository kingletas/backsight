"""Which stacks have been left behind by something upstream of them.

**This is what a Stacks section in the file rail was for, and it is the only
part of it worth anybody's attention.** A stack whose upstream has been applied
since this one was last planned is reading data that no longer describes the
world — and the plan you are looking at was computed from it.

The rail said nothing about that. It listed every stack, in order, every day,
whether or not any of it mattered; three quiet rows in the corner of a window
is a channel people stop reading, and then it is still unread on the day one of
them is not quiet. So the answer is a chip that is **absent until a stack is
actually stale**, and this module is what decides that.

The times come from the activity log, which already holds every plan and every
apply with a timestamp — a second record of the same events is a second record
that can disagree with the first. It is handed in as plain events rather than
read from there, because a stack parses, validates and graphs entirely offline
and reaches nothing: whoever owns both is the one allowed to join them.
"""

from __future__ import annotations

from dataclasses import dataclass

from backsight.engine.stacks.model import Definitions

PLANNED = "planned"
APPLIED = "applied"


@dataclass(frozen=True)
class Event:
    """One thing that happened to one stack, and when.

    `kind` is `planned` or `applied`; anything else is something this module
    has no opinion about.
    """

    kind: str
    stack: str
    at: str


@dataclass(frozen=True)
class Stale:
    """One stack whose plan predates an apply it depends on."""

    stack: str
    # The upstream stacks applied since this one was planned, newest first.
    behind: tuple[str, ...]
    # Nothing has ever been planned here, so there is no plan to be stale. The
    # stack is still waiting: an upstream moved and this one has not looked.
    never_planned: bool = False

    def __str__(self) -> str:
        if self.never_planned:
            return f"{self.stack} has never been planned since {self.behind[0]} was applied"
        return f"{self.stack} was planned before {', '.join(self.behind)} was applied"


def stale(definitions: Definitions, entries: list[Event]) -> list[Stale]:
    """Every declared stack that is behind something it depends on.

    Empty on the ordinary day, which is the point: the chip that reads this is
    absent whenever this list is, and a chip that is only ever present when
    something is wrong is one people keep reading.
    """
    if not definitions.is_declared:
        return []
    applied = _latest(entries, APPLIED)
    planned = _latest(entries, PLANNED)

    found: list[Stale] = []
    for stack in definitions.stacks.values():
        upstream = [name for name in stack.upstream if name in applied]
        if not upstream:
            continue
        mine = planned.get(stack.name)
        behind = tuple(
            sorted(
                (name for name in upstream if mine is None or applied[name] > mine),
                key=lambda name: applied[name],
                reverse=True,
            )
        )
        if behind:
            found.append(Stale(stack=stack.name, behind=behind, never_planned=mine is None))
    return sorted(found, key=lambda one: one.stack)


def _latest(entries: list[Event], kind: str) -> dict[str, str]:
    """The most recent timestamp per stack, for one kind of event.

    The window writes the stack name onto every plan and every apply it runs
    on a module that belongs to a declared stack. An entry with no stack name
    is about a module nobody has grouped, and is not this module's business.
    """
    latest: dict[str, str] = {}
    for entry in entries:
        if entry.kind != kind or not entry.stack:
            continue
        name = entry.stack
        if name not in latest or entry.at > latest[name]:
            latest[name] = entry.at
    return latest
