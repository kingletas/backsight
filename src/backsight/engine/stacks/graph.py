"""What depends on what, in which order, and what a change reaches.

FR-STK-04, FR-STK-06 and FR-STK-08. All of it works on declared edges alone,
so all of it works offline and none of it needs credentials.

The blast radius is the half of dependency management that belongs on the
desktop: while editing a stack, which downstream stacks consume its outputs,
and specifically which of those outputs this change touches.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backsight.engine.stacks.model import Definitions, Stack


@dataclass(frozen=True)
class Cycle:
    """A loop in the graph, named rather than merely detected."""

    names: tuple[str, ...]

    def __str__(self) -> str:
        return " → ".join([*self.names, self.names[0]])


@dataclass(frozen=True)
class Consumer:
    """One downstream stack, and the edge that put it downstream.

    `outputs` belongs to `through`, not to the stack that changed. Beyond the
    first hop those are two different stacks, and a list of output names with
    no owner reads as if they all came from the change.
    """

    name: str
    through: str
    outputs: tuple[str, ...]
    # How many edges away. 1 is a direct consumer.
    distance: int = 1

    @property
    def is_direct(self) -> bool:
        return self.distance == 1

    def because(self) -> str:
        """Why this stack is in the radius, in one line."""
        if not self.outputs:
            return f"needs {self.through}"
        return f"consumes {self.through}.{', '.join(self.outputs)}"


@dataclass
class Radius:
    """What a change to one stack reaches."""

    stack: str
    consumers: list[Consumer] = field(default_factory=list)

    @property
    def direct(self) -> list[Consumer]:
        return [consumer for consumer in self.consumers if consumer.is_direct]

    @property
    def is_empty(self) -> bool:
        return not self.consumers

    def summary(self) -> str:
        """Only what is there. Nothing reads as a row of zeroes."""
        if self.is_empty:
            return "Nothing downstream consumes this"
        direct = len(self.direct)
        indirect = len(self.consumers) - direct
        said = [f"{direct} downstream" if direct else ""]
        if indirect:
            said.append(f"{indirect} further on")
        return " · ".join(part for part in said if part)


def cycles(definitions: Definitions) -> list[Cycle]:
    """Every cycle, each named by the stacks in it.

    "There is a cycle" is not actionable. The specific loop is — FR-STK-04.
    """
    found: list[Cycle] = []
    seen: set[frozenset[str]] = set()
    on_path: list[str] = []
    finished: set[str] = set()

    def walk(name: str) -> None:
        if name in on_path:
            loop = tuple(on_path[on_path.index(name) :])
            if frozenset(loop) not in seen:
                seen.add(frozenset(loop))
                found.append(Cycle(names=loop))
            return
        if name in finished:
            return
        on_path.append(name)
        stack = definitions.get(name)
        for upstream in stack.upstream if stack else ():
            if definitions.get(upstream) is not None:
                walk(upstream)
        on_path.pop()
        finished.add(name)

    for name in sorted(definitions.stacks):
        walk(name)
    return found


def order(definitions: Definitions) -> list[str]:
    """Apply order: every stack after the ones it needs — FR-STK-08.

    A stack caught in a cycle is left out rather than placed arbitrarily. An
    order that quietly includes a cycle is an order somebody will follow.
    """
    caught = {name for cycle in cycles(definitions) for name in cycle.names}
    remaining = {
        name: {up for up in stack.upstream if up in definitions.stacks and up not in caught}
        for name, stack in definitions.stacks.items()
        if name not in caught
    }
    placed: list[str] = []
    while remaining:
        ready = sorted(name for name, needs in remaining.items() if not needs - set(placed))
        if not ready:
            break
        placed.extend(ready)
        for name in ready:
            remaining.pop(name)
    return placed


def consumers_of(definitions: Definitions, name: str) -> Radius:
    """Everything downstream of a stack, nearest first — FR-STK-06."""
    return _radius(definitions, name, changed=None)


def radius_of_change(definitions: Definitions, name: str, outputs: tuple[str, ...]) -> Radius:
    """Only the consumers of the outputs this change actually touches.

    A change that alters no published output reaches nothing, and saying so is
    the difference between a useful blast radius and a permanent warning.
    """
    return _radius(definitions, name, changed=set(outputs))


def _radius(definitions: Definitions, name: str, changed: set[str] | None) -> Radius:
    if definitions.get(name) is None:
        return Radius(stack=name)

    found: dict[str, Consumer] = {}
    frontier = {name: changed}
    distance = 0

    while frontier:
        distance += 1
        following: dict[str, set[str] | None] = {}
        for upstream, wanted in frontier.items():
            for stack in definitions.stacks.values():
                consumed = stack.needs.get(upstream)
                if not consumed:
                    continue
                touched = (
                    tuple(sorted(consumed))
                    if wanted is None
                    else tuple(sorted(set(consumed) & wanted))
                )
                if wanted is not None and not touched:
                    continue
                if stack.name in found or stack.name == name:
                    continue
                found[stack.name] = Consumer(
                    name=stack.name, through=upstream, outputs=touched, distance=distance
                )
                # Beyond the first hop the specific outputs are no longer the
                # question: a stack that changes because its input changed can
                # change any of its own outputs.
                following[stack.name] = None
        frontier = following

    return Radius(stack=name, consumers=sorted(found.values(), key=lambda c: (c.distance, c.name)))


def downstream_names(definitions: Definitions, name: str) -> list[str]:
    return [consumer.name for consumer in consumers_of(definitions, name).consumers]


def stacks_in_order(definitions: Definitions) -> list[Stack]:
    """The stacks themselves, in apply order, then anything left out."""
    placed = order(definitions)
    rest = sorted(set(definitions.stacks) - set(placed))
    return [definitions.stacks[name] for name in [*placed, *rest]]
