"""The infrastructure as it will be, built from a plan.

FR-EXP-01. Existing scanners look at the diff, which is why they miss exposure
that emerges from a new rule meeting a subnet that was already there. A plan's
`planned_values` is the whole projected world — everything that will exist, not
only what changed — so that is what this reads.

**Edges come from references, not from resolved values.** In a plan an id is
`(known after apply)`, so an analysis that waited for real ids could only ever
run after the damage. The configuration says `security_groups` points at
`aws_security_group.db`, and that is knowable now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# `aws_subnet.public.id` names the resource `aws_subnet.public`. A reference to
# a variable or a local names nothing in this graph.
NOT_RESOURCES = ("var.", "local.", "each.", "count.", "path.", "terraform.")


@dataclass(frozen=True)
class Node:
    """One resource as it will exist."""

    address: str
    type: str
    name: str
    values: dict[str, Any] = field(default_factory=dict)
    module: str = ""

    def value(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)


@dataclass(frozen=True)
class Edge:
    """One resource referring to another, and the attribute that does it."""

    source: str
    target: str
    via: str


@dataclass
class Graph:
    """Every resource that will exist, and what points at what."""

    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    unresolved: set[str] = field(default_factory=set)

    @property
    def is_partial(self) -> bool:
        """Whether a *reference* names something not in this configuration.

        This is only half of incompleteness, and the smaller half. A resource
        whose `subnet_id` is a literal `subnet-0123…` refers to something real
        that is not here, and no reference is involved — so nothing here can see
        it. Deciding that needs to know which attributes point at what, which is
        AWS knowledge and belongs to the analyser rather than to a graph.

        FR-EXP-08 is answered there. Reading this alone as "the graph is
        complete" is exactly the silent false negative it warns about.
        """
        return bool(self.unresolved)

    def of_type(self, type_: str) -> list[Node]:
        return [n for n in self.nodes.values() if n.type == type_]

    def targets_of(self, address: str, via: str | None = None) -> list[Node]:
        """What this resource points at."""
        return [
            self.nodes[e.target]
            for e in self.edges
            if e.source == address and e.target in self.nodes and (via is None or e.via == via)
        ]

    def sources_to(self, address: str, via: str | None = None) -> list[Node]:
        """What points at this resource."""
        return [
            self.nodes[e.source]
            for e in self.edges
            if e.target == address and e.source in self.nodes and (via is None or e.via == via)
        ]


def _resource_address(reference: str) -> str | None:
    """The resource an expression reference names, or nothing.

    `aws_subnet.public.id` and `aws_subnet.public` both name the subnet. A
    reference with only one segment names a whole resource type and nothing in
    particular, so it is not an edge.
    """
    if reference.startswith(NOT_RESOURCES):
        return None
    parts = reference.split(".")
    if len(parts) < 2:
        return None
    if parts[0] == "data":
        return ".".join(parts[:3]) if len(parts) >= 3 else None
    if parts[0] == "module":
        return ".".join(parts[:2])
    return f"{parts[0]}.{parts[1]}"


def _values_from(module: dict[str, Any], prefix: str = "") -> dict[str, Node]:
    found: dict[str, Node] = {}
    for entry in module.get("resources") or []:
        address = entry["address"]
        found[address] = Node(
            address=address,
            type=entry.get("type", ""),
            name=entry.get("name", ""),
            values=dict(entry.get("values") or {}),
            module=prefix,
        )
    for child in module.get("child_modules") or []:
        found.update(_values_from(child, prefix=child.get("address", "")))
    return found


def _edges_from(module: dict[str, Any], known: set[str]) -> tuple[list[Edge], set[str]]:
    edges: list[Edge] = []
    unresolved: set[str] = set()
    for entry in module.get("resources") or []:
        source = entry["address"]
        for attribute, expression in (entry.get("expressions") or {}).items():
            for reference in _references_in(expression):
                target = _resource_address(reference)
                if target is None or target == source:
                    continue
                if target in known:
                    if not any(
                        e.source == source and e.target == target and e.via == attribute
                        for e in edges
                    ):
                        edges.append(Edge(source=source, target=target, via=attribute))
                else:
                    unresolved.add(target)
    for child in (module.get("module_calls") or {}).values():
        inner, missing = _edges_from(child.get("module") or {}, known)
        edges.extend(inner)
        unresolved |= missing
    return edges, unresolved


def _references_in(expression: Any) -> list[str]:
    """Every reference an expression carries, however it is nested."""
    found: list[str] = []
    if isinstance(expression, dict):
        found.extend(expression.get("references") or [])
        for value in expression.values():
            if isinstance(value, dict | list):
                found.extend(_references_in(value))
    elif isinstance(expression, list):
        for item in expression:
            found.extend(_references_in(item))
    return found


def project(document: dict[str, Any]) -> Graph:
    """The world as the plan says it will be."""
    planned = (document.get("planned_values") or {}).get("root_module") or {}
    nodes = _values_from(planned)
    configuration = (document.get("configuration") or {}).get("root_module") or {}
    edges, unresolved = _edges_from(configuration, set(nodes))
    return Graph(nodes=nodes, edges=edges, unresolved=unresolved)
