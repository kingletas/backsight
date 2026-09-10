"""What an expression actually became, and what must never be shown.

The design and BRD §6.13. HCL cannot be stepped through, so debugging today means
adding an output and re-planning. All of this is derivable from the plan
Backsight already holds.

> [!danger]
> **A plan file contains sensitive values in plain text.** `"after": {"input":
> "hunter2"}` sits beside `"after_sensitive": {"input": true}`. Anything that
> displays a planned value and forgets to consult the second one leaks the
> first.
>
> So FR-DBG-06 is enforced by the type rather than by remembering: a `Resolved`
> for a sensitive attribute has no way to hand back its value. There is no flag,
> no setting and no argument that turns it on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# `aws_subnet.this["eu-west-1a"]` and `aws_subnet.this[0]`.
INDEXED = re.compile(r"^(?P<address>.+?)\[(?P<key>.+)\]$")

SENSITIVE = "(sensitive — not shown)"
UNKNOWN = "unknown until apply"


@dataclass(frozen=True)
class Resolved:
    """One attribute, as the plan says it will be.

    The value is private on purpose. `display` is the only way out, and it
    refuses for anything the plan marked sensitive.
    """

    attribute: str
    _value: Any = None
    known: bool = True
    sensitive: bool = False

    @property
    def display(self) -> str:
        """What may be shown. There is no other accessor, deliberately."""
        if self.sensitive:
            return SENSITIVE
        if not self.known:
            return UNKNOWN
        if isinstance(self._value, str):
            return f'"{self._value}"'
        if self._value is None:
            return "null"
        return str(self._value)

    @property
    def is_showable(self) -> bool:
        return self.known and not self.sensitive


@dataclass(frozen=True)
class Expansion:
    """What a `count` or `for_each` expanded to, before anything is applied.

    FR-DBG-03: expansion surprises are the largest single source of confusion in
    HCL, and the key set is computable in advance.
    """

    address: str
    keys: tuple[str, ...] = ()
    by_count: bool = False

    @property
    def instances(self) -> int:
        return len(self.keys)

    def summary(self) -> str:
        if not self.keys:
            return "no instances"
        noun = "instance" if self.instances == 1 else "instances"
        if self.by_count:
            return f"{self.instances} {noun}"
        listed = ", ".join(f'"{key}"' for key in self.keys)
        return f"{self.instances} {noun} · keys {listed}"


def _planned(document: dict[str, Any]) -> list[dict[str, Any]]:
    def walk(module: dict[str, Any]) -> list[dict[str, Any]]:
        found = list(module.get("resources") or [])
        for child in module.get("child_modules") or []:
            found.extend(walk(child))
        return found

    return walk((document.get("planned_values") or {}).get("root_module") or {})


def _base(address: str) -> str:
    match = INDEXED.match(address)
    return match.group("address") if match else address


def expansion(document: dict[str, Any], address: str) -> Expansion:
    """Every instance one declaration will produce, and how it is keyed."""
    wanted = _base(address)
    keys: list[str] = []
    by_count = False
    for entry in _planned(document):
        if _base(entry["address"]) != wanted:
            continue
        index = entry.get("index")
        if index is None:
            continue
        by_count = by_count or isinstance(index, int)
        keys.append(str(index))
    return Expansion(address=wanted, keys=tuple(keys), by_count=by_count)


def resolved(document: dict[str, Any], address: str, attribute: str) -> Resolved | None:
    """What one attribute of one resource will be, as far as the plan knows."""
    for change in document.get("resource_changes") or []:
        if change.get("address") != address:
            continue
        body = change.get("change") or {}
        after = body.get("after") or {}
        unknown = body.get("after_unknown") or {}
        sensitive = body.get("after_sensitive") or {}
        if attribute not in after and attribute not in unknown:
            return None
        return Resolved(
            attribute=attribute,
            _value=after.get(attribute),
            known=unknown.get(attribute) is not True,
            sensitive=_marked(sensitive, attribute),
        )
    return None


def _marked(sensitive: Any, attribute: str) -> bool:
    if sensitive is True:
        return True
    return isinstance(sensitive, dict) and bool(sensitive.get(attribute))


def all_resolved(document: dict[str, Any], address: str) -> list[Resolved]:
    """Every attribute of one resource, sensitive ones included but not shown."""
    for change in document.get("resource_changes") or []:
        if change.get("address") != address:
            continue
        body = change.get("change") or {}
        names = sorted(set(body.get("after") or {}) | set(body.get("after_unknown") or {}))
        found = [resolved(document, address, name) for name in names]
        return [item for item in found if item is not None]
    return []
