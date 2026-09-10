"""What a change does to the monthly bill, and when that cannot be said.

The rule this is built around: **a resource whose cost depends on usage is
marked as not estimable, never reported as zero** — FR-POL-06. A bill that says
nothing is a bill somebody checks; a bill that says zero is one they trust.

**No prices ship with this application.** A price invented from memory is a
confident number about somebody else's money, and there is no worse thing this
could do. AWS publishes its own — one region of EC2 alone is 482 MB — so the
table is built by importing that once, and until somebody does, the answer is
that there are no prices rather than that there is no cost.

`terraform_data` and the other engine-owned resources are the exception, and
they are free because they are nothing: no object exists anywhere to be billed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from backsight.engine.plan.model import Action, Plan

FILE = "prices.json"

# Resources the engine itself owns. Not "priced at zero" — there is no object
# anywhere for anybody to bill, which is a different statement.
NOTHING_TO_BILL = ("terraform_data", "null_resource", "random_", "local_", "time_", "tls_")


class Known(Enum):
    """How much is actually known about one resource's cost."""

    PRICED = "priced"
    FREE = "nothing to bill"
    USAGE = "depends on usage"
    UNKNOWN = "no price for this type"


@dataclass(frozen=True)
class Line:
    """One resource, and what it does to the bill."""

    address: str
    type: str
    action: Action
    known: Known = Known.UNKNOWN
    before: float = 0.0
    after: float = 0.0

    @property
    def difference(self) -> float:
        return round(self.after - self.before, 2)

    @property
    def is_estimable(self) -> bool:
        return self.known in (Known.PRICED, Known.FREE)

    @property
    def summary(self) -> str:
        if self.known is Known.FREE:
            return f"{self.address} — nothing to bill"
        if not self.is_estimable:
            return f"{self.address} — {self.known.value}"
        sign = "+" if self.difference > 0 else ""
        return f"{self.address} — {sign}{self.difference:.2f}"


@dataclass
class Estimate:
    """What the plan does to the monthly bill, and what it could not say."""

    lines: tuple[Line, ...] = ()
    currency: str = "USD"
    have_prices: bool = False

    @property
    def difference(self) -> float:
        return round(sum(one.difference for one in self.lines if one.is_estimable), 2)

    @property
    def unestimable(self) -> tuple[Line, ...]:
        return tuple(one for one in self.lines if not one.is_estimable)

    @property
    def is_complete(self) -> bool:
        return bool(self.lines) and not self.unestimable

    @property
    def headline(self) -> str:
        """Never a number this does not have. A tilde where it is a guess."""
        if not self.lines:
            return "Nothing in this plan costs anything"
        if not self.have_prices:
            return "No prices imported yet, so nothing can be estimated"
        if not any(one.known is Known.PRICED for one in self.lines):
            return "Nothing here is priced"
        sign = "+" if self.difference > 0 else ""
        said = f"{sign}{self.difference:.2f} {self.currency} a month"
        if self.unestimable:
            count = len(self.unestimable)
            return f"~{said}, and {count} that cannot be estimated"
        return said

    @property
    def chip(self) -> tuple[str, str]:
        """The verdict line's cost chip, as text and a direction arrow.

        Empty when there is nothing honest to put in it — no prices, or nothing
        priced. **A chip with nothing to say is absent, not empty**, and a chip
        reading "prices are not configured" would fire on every plan forever.

        A delta carries a direction: a signed number with no arrow reads as a
        total, and the difference between "the bill is 124" and "the bill goes
        up by 124" is the whole of what this says.
        """
        if not self.have_prices or not any(one.known is Known.PRICED for one in self.lines):
            return "", ""
        amount = abs(self.difference)
        about = "~" if self.unestimable else ""
        if self.difference == 0:
            return f"{about}{_money(amount, self.currency)}/mo", ""
        return f"{about}{_money(amount, self.currency)}/mo", "↑" if self.difference > 0 else "↓"


def _money(amount: float, currency: str) -> str:
    """A figure a person reads, rather than a float."""
    symbol = {"USD": "$", "EUR": "€", "GBP": "£"}.get(currency, "")
    said = f"{amount:,.2f}".rstrip("0").rstrip(".")
    return f"{symbol}{said}" if symbol else f"{said} {currency}"


def directory(home: Path | None = None) -> Path:
    if home is not None:
        return Path(home) / ".local" / "share" / "backsight"
    root = os.environ.get("XDG_DATA_HOME")
    base = Path(root) if root else Path.home() / ".local" / "share"
    return base / "backsight"


@dataclass
class Prices:
    """Monthly prices by resource type, from a table somebody imported."""

    monthly: dict[str, float] = field(default_factory=dict)
    # Types whose cost is per-request, per-GB or per-hour-of-something, so a
    # monthly figure would be a fiction rather than an estimate.
    by_usage: frozenset[str] = frozenset()
    currency: str = "USD"

    @property
    def any(self) -> bool:
        return bool(self.monthly)

    def known_for(self, type_: str) -> Known:
        if type_.startswith(NOTHING_TO_BILL):
            return Known.FREE
        if type_ in self.by_usage:
            return Known.USAGE
        return Known.PRICED if type_ in self.monthly else Known.UNKNOWN

    def monthly_for(self, type_: str) -> float:
        return float(self.monthly.get(type_, 0.0))


def load(home: Path | None = None) -> Prices:
    """The imported table, or an empty one. Empty is the ordinary state."""
    try:
        stored = json.loads((directory(home) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Prices()
    if not isinstance(stored, dict):
        return Prices()
    monthly = {
        str(key): float(value)
        for key, value in (stored.get("monthly") or {}).items()
        if isinstance(value, int | float)
    }
    return Prices(
        monthly=monthly,
        by_usage=frozenset(str(one) for one in stored.get("by_usage") or []),
        currency=str(stored.get("currency", "USD")),
    )


def estimate(plan: Plan | None, prices: Prices) -> Estimate:
    """What this plan does to the bill, resource by resource."""
    if plan is None:
        return Estimate(have_prices=prices.any, currency=prices.currency)

    lines = []
    for change in plan.changes:
        if change.action is Action.NO_OP:
            continue
        known = prices.known_for(change.type)
        monthly = prices.monthly_for(change.type)
        before = monthly if change.action in (Action.UPDATE, Action.REPLACE, Action.DELETE) else 0.0
        after = monthly if change.action in (Action.CREATE, Action.UPDATE, Action.REPLACE) else 0.0
        lines.append(
            Line(
                address=change.address,
                type=change.type,
                action=change.action,
                known=known,
                before=before if known is Known.PRICED else 0.0,
                after=after if known is Known.PRICED else 0.0,
            )
        )
    return Estimate(lines=tuple(lines), currency=prices.currency, have_prices=prices.any)
