"""What can be written at the cursor, answered from the local schema index.

FR-SCH-09 and FR-SCH-10. The position is worked out from the syntax tree rather
than from the characters to the left of the cursor, because `name = "` inside a
string and `name = ` at an argument are the same characters and different
questions.

What is offered is only what the schema actually declares. It has no enumerated
values, no defaults and no force-replacement flag, so none of those appear here;
see `docs/decisions/001-...`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from backsight.engine.hcl import parse
from backsight.engine.schema.index import SchemaIndex

# The blocks a file can open with. `locals` and `terraform` take no label.
TOP_LEVEL = (
    ("resource", "a managed resource"),
    ("data", "a read-only lookup"),
    ("module", "a call to another module"),
    ("variable", "an input to this module"),
    ("output", "a value this module returns"),
    ("locals", "named values used in this module"),
    ("provider", "provider configuration"),
    ("terraform", "settings, backend and provider requirements"),
    ("moved", "tells the state an address changed"),
    ("import", "brings an existing object under management"),
    ("check", "an assertion evaluated after apply"),
)

WORD = re.compile(rb"[A-Za-z0-9_]+$")

# Terraform owns `id` on every resource. Most providers still declare it as
# optional for historical reasons, so the schema alone would offer it as
# something to write, and writing it does nothing.
RESERVED = ("id",)


class Kind(Enum):
    """What sort of thing the cursor is in a position to receive."""

    TOP_LEVEL = "top level"
    RESOURCE_TYPE = "resource type"
    DATA_TYPE = "data source type"
    ARGUMENT = "argument"
    VALUE = "value"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Context:
    """Where the cursor is, in terms the index can answer."""

    kind: Kind
    prefix: str = ""
    resource_type: str | None = None
    resource_name: str | None = None
    resource_kind: str = "resource"
    path: str = ""

    @property
    def address(self) -> str | None:
        """The address a plan would use for this resource, when there is one."""
        if not self.resource_type or not self.resource_name:
            return None
        prefix = "" if self.resource_kind == "resource" else "data."
        return f"{prefix}{self.resource_type}.{self.resource_name}"


@dataclass(frozen=True)
class Candidate:
    """One thing that could be written here."""

    label: str
    kind: Kind
    required: bool = False
    type_label: str = ""
    description: str = ""
    detail: str = ""

    @property
    def sort_key(self) -> tuple[int, str]:
        """Required arguments first, then alphabetical.

        FR-SCH-09 wants required visually distinct from optional. Ordering is
        half of that; the interface does the other half.
        """
        return (0 if self.required else 1, self.label)


def _probe(source: bytes, offset: int) -> tuple[bytes, int, str]:
    """The buffer with the half-typed word removed, and that word.

    Completion always runs on incomplete text, and a half-typed identifier makes
    tree-sitter fail the whole file rather than the line: `desc` on its own turns
    the entire config into one error node with no blocks in it. Taking the word
    out first gives a tree to read, and the word is what filters the answer.
    """
    match = WORD.search(source[:offset])
    if match is None:
        return source, offset, ""
    word = match.group()
    start = offset - len(word)
    return source[:start] + source[offset:], start, word.decode("utf-8")


def _containing_blocks(source: bytes, offset: int) -> list[parse.Block]:
    """The chain of blocks the offset sits inside, outermost first."""
    chain: list[parse.Block] = []
    body = parse.body_of(source)
    while body is not None:
        found = None
        for block in parse.blocks(body, source):
            if block.node.start_byte <= offset <= block.node.end_byte:
                found = block
                break
        if found is None:
            return chain
        chain.append(found)
        body = found.body
    return chain


def _in_a_value(block: parse.Block, offset: int) -> bool:
    """Whether the offset sits in the value half of an attribute.

    `engine = "` and a blank line inside the same block are both "somewhere in a
    resource body", and only one of them wants argument names.
    """
    body = block.body
    if body is None:
        return False
    for child in body.children:
        if child.type != "attribute":
            continue
        expression = next((c for c in child.children if c.type == "expression"), None)
        if expression is not None and expression.start_byte <= offset <= expression.end_byte:
            return True
    return False


def _in_first_label(block: parse.Block, source: bytes, offset: int) -> bool:
    """Whether the cursor is inside the block's first quoted label."""
    labels = [c for c in block.node.children if c.type == "string_lit"]
    if not labels:
        return False
    return labels[0].start_byte <= offset <= labels[0].end_byte


def context_at(source: bytes, offset: int) -> Context:
    """Reads the cursor position as a question the index can answer."""
    offset = max(0, min(offset, len(source)))
    source, offset, prefix = _probe(source, offset)
    chain = _containing_blocks(source, offset)

    if not chain:
        return Context(kind=Kind.TOP_LEVEL, prefix=prefix)

    outer = chain[0]
    if outer.type in ("resource", "data") and _in_first_label(outer, source, offset):
        kind = Kind.RESOURCE_TYPE if outer.type == "resource" else Kind.DATA_TYPE
        # Inside quotes the word regex stops at the quote, which is what we want.
        return Context(kind=kind, prefix=prefix)

    if outer.type not in ("resource", "data"):
        return Context(kind=Kind.UNKNOWN, prefix=prefix)
    if not outer.labels:
        return Context(kind=Kind.UNKNOWN, prefix=prefix)

    if _in_a_value(chain[-1], offset):
        return Context(kind=Kind.VALUE, prefix=prefix)

    # Nested blocks give the path the index stores attributes under.
    path = ".".join(block.type for block in chain[1:])
    return Context(
        kind=Kind.ARGUMENT,
        prefix=prefix,
        resource_type=outer.labels[0],
        resource_name=outer.labels[1] if len(outer.labels) > 1 else None,
        resource_kind="resource" if outer.type == "resource" else "data",
        path=path,
    )


def complete(
    source: bytes,
    offset: int,
    index: SchemaIndex,
    *,
    provider_version: str | None = None,
    limit: int = 200,
) -> list[Candidate]:
    """Everything that could be written at this offset, best first."""
    context = context_at(source, offset)

    if context.kind is Kind.TOP_LEVEL:
        return [
            Candidate(label=name, kind=Kind.TOP_LEVEL, description=description)
            for name, description in TOP_LEVEL
            if name.startswith(context.prefix)
        ][:limit]

    if context.kind in (Kind.RESOURCE_TYPE, Kind.DATA_TYPE):
        kind = "resource" if context.kind is Kind.RESOURCE_TYPE else "data"
        return [
            Candidate(label=name, kind=context.kind)
            for name in index.resource_types(context.prefix, kind=kind, limit=limit)
        ]

    if context.kind is Kind.VALUE:
        # The schema declares no enumerated values, so there is nothing truthful
        # to offer here. Guessing a list would be worse than an empty one.
        return []

    if context.kind is not Kind.ARGUMENT or context.resource_type is None:
        return []

    candidates = [
        Candidate(
            label=attribute.name,
            kind=Kind.ARGUMENT,
            required=attribute.required,
            type_label=attribute.type_label,
            description=attribute.description,
            detail="required" if attribute.required else "optional",
        )
        for attribute in index.attributes(
            context.resource_type,
            kind=context.resource_kind,
            path=context.path,
            provider_version=provider_version,
        )
        # An attribute the provider computes is not something to write. It is
        # worth completing as a reference elsewhere, never as an argument here.
        if not attribute.is_read_only and attribute.name not in RESERVED
    ]
    candidates += [
        Candidate(
            label=block.name,
            kind=Kind.ARGUMENT,
            required=bool(block.min_items),
            type_label=f"{block.nesting} block",
            detail="block",
        )
        for block in index.nested_blocks(
            context.resource_type, kind=context.resource_kind, path=context.path
        )
    ]
    matching = [c for c in candidates if c.label.startswith(context.prefix)]
    return sorted(matching, key=lambda c: c.sort_key)[:limit]
