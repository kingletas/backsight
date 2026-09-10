"""Why is this being replaced.

FR-DBG-05. The plan states *that* a resource will be
destroyed and recreated. It does not say which of your edits caused it, and that
is the question somebody actually has.

The trace ends at an edit rather than at an attribute. Naming the attribute is
where every other tool stops; naming the variable it came from is what makes it
actionable.

It also names what else will notice. A replaced resource gets a new id, and
everything holding that id sees an update the plan shows without explaining the
connection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backsight.engine.insight.graph import _resource_address
from backsight.engine.plan.model import Action, Plan


@dataclass(frozen=True)
class Step:
    """One link in the chain, in the words a person reads."""

    text: str
    detail: str = ""

    def __str__(self) -> str:
        return f"{self.text} — {self.detail}" if self.detail else self.text


@dataclass
class Trace:
    """Why one resource is being replaced, and what else will notice."""

    address: str
    attributes: tuple[str, ...] = ()
    steps: list[Step] = field(default_factory=list)
    downstream: tuple[str, ...] = ()

    @property
    def is_explained(self) -> bool:
        """Whether the plan named an attribute at all."""
        return bool(self.attributes)

    def lines(self) -> list[str]:
        return [str(step) for step in self.steps]

    def consequence(self) -> str:
        """What the replacement will do to everything holding its id."""
        if not self.downstream:
            return "Nothing else in this plan depends on it."
        count = len(self.downstream)
        return f"{count} resource{'' if count == 1 else 's'} depend on this and will see a new id."


def _configuration(document: dict[str, Any]) -> list[dict[str, Any]]:
    root = (document.get("configuration") or {}).get("root_module") or {}
    return list(root.get("resources") or [])


def _expression_for(document: dict[str, Any], address: str, attribute: str) -> list[str]:
    """What the configuration says produces this attribute."""
    for entry in _configuration(document):
        if entry.get("address") != address:
            continue
        expression = (entry.get("expressions") or {}).get(attribute) or {}
        return list(expression.get("references") or [])
    return []


def _depends_on(document: dict[str, Any], address: str) -> tuple[str, ...]:
    """Everything whose configuration refers to this resource."""
    found = []
    for entry in _configuration(document):
        if entry.get("address") == address:
            continue
        for expression in (entry.get("expressions") or {}).values():
            references = expression.get("references") if isinstance(expression, dict) else None
            for reference in references or []:
                if _resource_address(reference) == address:
                    found.append(entry["address"])
                    break
            else:
                continue
            break
    return tuple(sorted(set(found)))


def replacement_trace(plan: Plan, document: dict[str, Any], address: str) -> Trace | None:
    """The chain from a replacement back to the edit that caused it."""
    change = plan.change_at(address)
    if change is None or change.action is not Action.REPLACE:
        return None

    trace = Trace(address=address, attributes=change.replacing_attributes)
    trace.steps.append(Step(f"{address}", "will be destroyed and recreated"))

    if not change.replacing_attributes:
        # The plan says it is replaced and does not say why. Saying so is better
        # than inventing a cause.
        trace.steps.append(Step("the plan does not name an attribute", change.action_reason or ""))
        trace.downstream = _depends_on(document, address)
        return trace

    for attribute in change.replacing_attributes:
        trace.steps.append(Step(f"forced by {attribute}", "cannot be changed in place"))
        before = change.attribute(attribute)
        if before is not None and before.changed and not before.sensitive:
            trace.steps.append(Step("changed", f"{_shown(before.before)} → {_shown(before.after)}"))
        elif before is not None and before.sensitive:
            trace.steps.append(Step("changed", "(sensitive — not shown)"))
        for reference in _expression_for(document, address, attribute):
            trace.steps.append(Step(f"value from {reference}"))

    trace.downstream = _depends_on(document, address)
    return trace


def _shown(value: Any) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    return "null" if value is None else str(value)
