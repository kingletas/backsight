"""A plan, arranged for reading.

Kept out of the window so the arrangement can be tested without a display, and
so a second front end cannot end up describing the same plan differently.
"""

from __future__ import annotations

from dataclasses import dataclass

from backsight.engine.plan.model import Action, Plan, ResourceChange
from backsight.engine.presentation import language


@dataclass(frozen=True)
class Row:
    """One resource, as a person reads it."""

    address: str
    action: Action
    mark: str
    label: str
    tone: str
    module: str = ""
    reason: str = ""
    # Where it was written, so a row is somewhere you can go rather than a
    # string you have to search for.
    where: str = ""
    # What it does to the monthly bill, when that is knowable. Empty rather
    # than nought: rounding a usage-priced resource to zero is a confident
    # claim about somebody's money.
    cost: str = ""

    @property
    def needs_a_second_look(self) -> bool:
        return self.action.destroys


def _reason(change: ResourceChange) -> str:
    """Why, in a sentence, when the plan gives a why."""
    if change.action is not Action.REPLACE:
        return ""
    causes = change.replacing_attributes
    if causes:
        joined = ", ".join(causes)
        return f"replaced because {joined} cannot be changed in place"
    if change.action_reason:
        # The plan's own vocabulary, made readable rather than reprinted raw.
        return change.action_reason.replace("_", " ")
    return "replaced; the plan does not say which attribute caused it"


def rows(plan: Plan, *, source_map=None, estimate=None) -> list[Row]:
    """Every change worth showing, destructive ones first.

    A reviewer's attention is finite and the destroys are what it is for, so they
    are not left to be found somewhere down an alphabetical list.

    A row answers four questions: **what it is, where it was written, why the
    plan is doing this, and what it costs.** The last two are absent rather
    than invented when the plan does not say — but the first two are always
    knowable, and a row without them is a string somebody has to go and search
    for.
    """
    priced = {line.address: line for line in (estimate.lines if estimate is not None else ())}
    found = []
    for change in plan.effective:
        label, mark, tone = language.ACTIONS[change.action.value]
        found.append(
            Row(
                address=change.address,
                action=change.action,
                mark=mark,
                label=label,
                tone=tone,
                module=change.module,
                reason=_reason(change),
                where=_where(change.address, source_map),
                cost=_cost(priced.get(change.address)),
            )
        )
    order = {Action.DELETE: 0, Action.REPLACE: 1, Action.UPDATE: 2, Action.CREATE: 3}
    return sorted(found, key=lambda row: (order.get(row.action, 4), row.address))


def _where(address: str, source_map) -> str:
    """`main.tf:42`, or nothing when the declaration is not in these files."""
    if source_map is None:
        return ""
    place = source_map.locate(address)
    return str(place) if place is not None else ""


def _cost(line) -> str:
    """What one resource does to the bill, or nothing when that is not knowable."""
    if line is None or not line.is_estimable:
        return ""
    if line.difference == 0:
        return ""
    sign = "+" if line.difference > 0 else ""
    return f"{sign}{line.difference:.2f} a month"


def headline(plan: Plan) -> str:
    """The one line above the list."""
    return plan.summary()


def warning(plan: Plan) -> str:
    """What to say above a plan that destroys something, or nothing at all.

    Both halves say "destroyed", so joining them with "and" produced "1 to be
    destroyed and 1 to be destroyed and recreated" — a sentence that reads as a
    stutter and makes the reader count the word rather than the resources.
    """
    counts = plan.counts()
    destroyed = counts.get(Action.DELETE, 0)
    replaced = counts.get(Action.REPLACE, 0)
    if not destroyed and not replaced:
        return ""
    if destroyed and replaced:
        return f"{destroyed + replaced} destroyed — {replaced} of them recreated after"
    if destroyed:
        return f"{destroyed} to be destroyed"
    return f"{replaced} to be destroyed and recreated"
