"""What holding the pointer over an attribute should say.

FR-SCH-05. Most of it comes from the schema. The one fact the schema cannot
supply — whether changing this attribute forces the resource to be replaced —
comes from the plan, by decision 001.

The distinction that matters here is between *no* and *not known yet*. With no
plan in hand this says the question is unanswered, and never that the attribute
is safe. An editor that quietly reports "does not force replacement" because it
has not looked is worse than one that says nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from backsight.engine.plan.model import Plan
from backsight.engine.schema.completion import Kind, context_at
from backsight.engine.schema.index import SchemaIndex

WORD_AT = re.compile(r"[A-Za-z0-9_]+")


class Replacement(Enum):
    """What is known about this attribute forcing a replacement."""

    FORCES = "forces replacement"
    DOES_NOT = "does not force replacement in this plan"
    UNKNOWN = "not known until a plan runs"


@dataclass(frozen=True)
class Hover:
    """Everything worth saying about the attribute under the pointer."""

    name: str
    resource_type: str
    type_label: str
    requirement: str
    description: str = ""
    deprecated: bool = False
    sensitive: bool = False
    replacement: Replacement = Replacement.UNKNOWN
    replacement_detail: str = ""

    @property
    def forces_replacement(self) -> bool:
        """Only ever true when a plan said so."""
        return self.replacement is Replacement.FORCES


def word_at(source: bytes, offset: int) -> tuple[str, int, int]:
    """The identifier the offset sits in or beside, and where it starts and ends.

    Expands both ways: hovering the middle of a word is the ordinary case, and
    the completion probe's look-behind would return half of it.
    """
    text = source.decode("utf-8", "replace")
    offset = max(0, min(offset, len(text)))
    for match in WORD_AT.finditer(text):
        if match.start() <= offset <= match.end():
            return match.group(), match.start(), match.end()
    return "", offset, offset


def hover_at(
    source: bytes,
    offset: int,
    index: SchemaIndex,
    *,
    plan: Plan | None = None,
    module_prefix: str = "",
    provider_version: str | None = None,
) -> Hover | None:
    """What to show for the attribute at this offset, or nothing."""
    name, start, _end = word_at(source, offset)
    if not name:
        return None

    # Ask for the position at the start of the word, so the context is the
    # argument rather than whatever follows the cursor.
    context = context_at(source, start)
    if context.kind is not Kind.ARGUMENT or context.resource_type is None:
        return None

    attribute = index.attribute(
        context.resource_type,
        name,
        kind=context.resource_kind,
        path=context.path,
        provider_version=provider_version,
    )
    if attribute is None:
        return None

    if attribute.required:
        requirement = "required"
    elif attribute.is_read_only:
        requirement = "read-only"
    else:
        requirement = "optional"

    replacement, detail = _replacement(context, name, plan, module_prefix)
    return Hover(
        name=name,
        resource_type=context.resource_type,
        type_label=attribute.type_label,
        requirement=requirement,
        description=attribute.description,
        deprecated=attribute.deprecated,
        sensitive=attribute.sensitive,
        replacement=replacement,
        replacement_detail=detail,
    )


def _replacement(context, name: str, plan: Plan | None, module_prefix: str):
    """Reads the plan, and says plainly when there is nothing to read."""
    address = context.address
    if plan is None or address is None:
        return Replacement.UNKNOWN, "Save the file to plan and find out."

    full = f"{module_prefix}.{address}" if module_prefix else address
    change = plan.change_at(full)
    if change is None:
        # The resource is not in this plan at all, so the plan says nothing
        # about it. That is not the same as saying the attribute is safe.
        return Replacement.UNKNOWN, "This resource is not in the current plan."

    if name in change.replacing_attributes:
        return (
            Replacement.FORCES,
            f"{full} is being replaced, and {name} is why.",
        )
    return (
        Replacement.DOES_NOT,
        f"In this plan {full} is not being replaced because of {name}.",
    )
