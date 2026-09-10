"""The line above a resource block: three facts you would otherwise gather.

The code lens. Reference count, plan action, cost — **off by default**,
because a line above every block is noise to anyone who does not want it.

Cost is absent rather than guessed. There is no pricing data in this product
yet, and a lens saying `$0/mo` about an instance would be worse than a lens
that says nothing about money at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from backsight.engine.insight.graph import Graph, project
from backsight.engine.insight.source_map import SourceMap

SEPARATOR = " · "

# What the plan is about to do, in the words the lens uses. Absent from the map
# means the plan does not touch this resource, which the lens says plainly.
ACTIONS = {
    "create": "added in plan",
    "update": "changed in plan",
    "delete": "destroyed in plan",
    "replace": "replaced in plan",
}

UNTOUCHED = "not in plan"


@dataclass(frozen=True)
class Lens:
    """One line, above one block."""

    line: int
    address: str
    references: int
    action: str

    @property
    def text(self) -> str:
        return SEPARATOR.join([_references(self.references), self.action])

    @property
    def without_action(self) -> str:
        """The lens with the plan action left out.

        The design puts the verdict in the gutter and the lens above the block,
        so they never sit together. Where they do share a line, "Add" and
        "added in plan" are the same sentence twice.
        """
        return _references(self.references)


def for_plan(document: dict, source_map: SourceMap) -> list[Lens]:
    """A lens for every resource the source map can place in a file.

    A resource the map cannot locate gets no lens rather than a lens on line 0.
    """
    graph = project(document)
    actions = _actions(document)
    found: list[Lens] = []
    for address, where in source_map.places.items():
        found.append(
            Lens(
                line=where.line,
                address=address,
                references=len(graph.sources_to(address)),
                action=actions.get(address, UNTOUCHED),
            )
        )
    return sorted(found, key=lambda lens: lens.line)


def in_file(lenses: list[Lens], path: str, source_map: SourceMap) -> list[Lens]:
    """Only the lenses whose block is in this file.

    Both sides are resolved before comparing: the map holds whatever path the
    workspace walk produced, and the editor holds whatever the person opened.
    A string comparison between those two silently matches nothing.
    """
    from pathlib import Path as _Path  # noqa: PLC0415

    wanted = _Path(path).resolve()
    return [
        lens
        for lens in lenses
        if (place := source_map.places.get(lens.address)) is not None
        and _Path(place.path).resolve() == wanted
    ]


def _actions(document: dict) -> dict[str, str]:
    """What the plan does to each address, by the lens's own vocabulary."""
    found: dict[str, str] = {}
    for change in document.get("resource_changes") or []:
        address = change.get("address")
        actions = (change.get("change") or {}).get("actions") or []
        if not address:
            continue
        found[address] = _describe(actions)
    return found


def _describe(actions: list[str]) -> str:
    """A replacement arrives as two actions, and it is one thing to a reader."""
    if "create" in actions and "delete" in actions:
        return ACTIONS["replace"]
    for name in ("delete", "create", "update"):
        if name in actions:
            return ACTIONS[name]
    return UNTOUCHED


def _references(count: int) -> str:
    if count == 0:
        return "no references"
    return f"{count} reference{'' if count == 1 else 's'}"


def references_to(graph: Graph, address: str) -> int:
    """How many resources refer to this one. Exposed for the hover and tests."""
    return len(graph.sources_to(address))
