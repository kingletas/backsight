"""A plan, read from `tofu show -json` and turned into something to render.

Two things here matter more than the rest. **Replacement is read, never
inferred** — the plan states both that a resource is being replaced and which
attribute path caused it, and guessing either from a before/after comparison is
how a workbench tells somebody the wrong resource is about to be destroyed.

And by decision 001, this is where force-replacement comes from at all: the
schema does not carry it, so `AttributeChange.forces_replacement` is the only
truthful source in the product.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# `module.vpc.module.subnets.aws_subnet.this[0]` -> the module part.
MODULE = re.compile(r"^((?:module\.[^.]+\.)+)")


class Action(Enum):
    """What the plan says will happen to one resource."""

    NO_OP = "no-op"
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    REPLACE = "replace"
    DELETE = "delete"

    @property
    def destroys(self) -> bool:
        """Whether the real object goes away. The two that need a second look."""
        return self in (Action.DELETE, Action.REPLACE)


@dataclass(frozen=True)
class AttributeChange:
    """One attribute inside a change, and whether it is the cause of a replacement."""

    name: str
    before: Any
    after: Any
    unknown: bool = False
    sensitive: bool = False
    forces_replacement: bool = False

    @property
    def changed(self) -> bool:
        return self.unknown or self.before != self.after


@dataclass(frozen=True)
class ResourceChange:
    """One resource the plan intends to touch."""

    address: str
    type: str
    name: str
    mode: str
    provider: str
    action: Action
    action_reason: str | None = None
    module: str = ""
    replace_paths: tuple[tuple[str, ...], ...] = ()
    attributes: tuple[AttributeChange, ...] = ()

    @property
    def replacing_attributes(self) -> tuple[str, ...]:
        """The attribute names the plan blames for a replacement."""
        return tuple(path[0] for path in self.replace_paths if path)

    def attribute(self, name: str) -> AttributeChange | None:
        return next((a for a in self.attributes if a.name == name), None)

    @property
    def changed_attributes(self) -> tuple[AttributeChange, ...]:
        return tuple(a for a in self.attributes if a.changed)


@dataclass(frozen=True)
class Plan:
    """Everything one plan says."""

    format_version: str
    engine_version: str
    errored: bool = False
    changes: tuple[ResourceChange, ...] = field(default=())

    @property
    def effective(self) -> tuple[ResourceChange, ...]:
        """The changes worth showing. A no-op is a fact, not a change."""
        return tuple(c for c in self.changes if c.action is not Action.NO_OP)

    def counts(self) -> dict[Action, int]:
        found: dict[Action, int] = {}
        for change in self.changes:
            found[change.action] = found.get(change.action, 0) + 1
        return found

    @property
    def is_destructive(self) -> bool:
        """FR-REF-03's question, asked in one place so every caller asks it the same."""
        return any(change.action.destroys for change in self.changes)

    def change_at(self, address: str) -> ResourceChange | None:
        return next((c for c in self.changes if c.address == address), None)

    def forces_replacement(self, address: str, attribute: str) -> bool:
        """Whether this attribute is why this resource is being replaced.

        Decision 001: the provider schema carries no such flag, so this is the
        only place in the product that can answer the question truthfully.
        """
        change = self.change_at(address)
        return bool(change and attribute in change.replacing_attributes)

    def summary(self) -> str:
        """The one line a header bar shows."""
        counts = self.counts()
        parts = [
            f"{counts[action]} to {word}"
            for action, word in (
                (Action.CREATE, "add"),
                (Action.UPDATE, "change"),
                (Action.REPLACE, "replace"),
                (Action.DELETE, "destroy"),
            )
            if counts.get(action)
        ]
        return ", ".join(parts) or "no changes"


def _action(actions: list[str]) -> Action:
    """Reads the action list, including both orderings of a replacement."""
    if sorted(actions) == ["create", "delete"]:
        return Action.REPLACE
    if len(actions) == 1:
        return Action(actions[0])
    raise ValueError(f"unrecognised plan actions: {actions}")


def _module_of(address: str) -> str:
    match = MODULE.match(address)
    return match.group(1).rstrip(".") if match else ""


def _attributes(change: dict[str, Any], replacing: set[str]) -> tuple[AttributeChange, ...]:
    before = change.get("before") or {}
    after = change.get("after") or {}
    unknown = change.get("after_unknown") or {}
    before_sensitive = change.get("before_sensitive") or {}
    after_sensitive = change.get("after_sensitive") or {}

    found = []
    for name in sorted(set(before) | set(after) | set(unknown)):
        found.append(
            AttributeChange(
                name=name,
                before=before.get(name),
                after=after.get(name),
                unknown=unknown.get(name) is True,
                sensitive=bool(_flagged(before_sensitive, name) or _flagged(after_sensitive, name)),
                forces_replacement=name in replacing,
            )
        )
    return tuple(found)


def _flagged(sensitive: Any, name: str) -> bool:
    """A sensitivity map is `true`, or a nested shape mirroring the value."""
    if sensitive is True:
        return True
    if isinstance(sensitive, dict):
        return name in sensitive
    return False


def parse(document: dict[str, Any]) -> Plan:
    """Turns one `tofu show -json` document into a plan."""
    changes = []
    for entry in document.get("resource_changes") or []:
        raw = entry.get("change") or {}
        paths = tuple(
            tuple(str(part) for part in path) for path in (raw.get("replace_paths") or [])
        )
        replacing = {path[0] for path in paths if path}
        changes.append(
            ResourceChange(
                address=entry["address"],
                type=entry.get("type", ""),
                name=entry.get("name", ""),
                mode=entry.get("mode", "managed"),
                provider=entry.get("provider_name", ""),
                action=_action(raw.get("actions") or ["no-op"]),
                action_reason=entry.get("action_reason"),
                module=_module_of(entry["address"]),
                replace_paths=paths,
                attributes=_attributes(raw, replacing),
            )
        )
    return Plan(
        format_version=document.get("format_version", ""),
        engine_version=document.get("terraform_version", ""),
        errored=bool(document.get("errored")),
        changes=tuple(changes),
    )


def read(path: Path) -> Plan:
    return parse(json.loads(Path(path).read_text(encoding="utf-8")))
