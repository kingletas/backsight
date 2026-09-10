"""Entries built from the provider schema, so every resource type has one.

Nobody writes a snippet for `aws_s3_bucket` before they need it, and by the
time they need it they are already typing the thing the snippet would have
saved. The schema already knows every argument, which is required, and what
type each one is — so the library is never empty for a resource somebody is
about to write.

Two per type, because the two questions are different. **The short one** is the
required arguments and nothing else, which is what somebody who knows the
resource wants. **The full one** is every argument with its type and a comment
saying whether it is optional, which is what somebody meeting it for the first
time wants instead of a documentation tab.
"""

from __future__ import annotations

import json

from backsight.engine.library.entry import Entry, Kind, Source

# Past this a generated entry is a wall rather than a starting point, and the
# documentation is the better answer.
MOST_ARGUMENTS = 40

# What a placeholder for one of these should say before anybody types.
BY_TYPE = {
    "string": '"${N}"',
    "number": "${N:0}",
    "bool": "${N:false}",
}


def _shape(declared: str) -> str:
    """The outermost type, out of the schema's own JSON encoding.

    A type arrives as `"string"` or `["list", "string"]` — JSON, not a word —
    and reading it as a word gave every argument a string placeholder including
    the numbers and the booleans.
    """
    try:
        found = json.loads(declared)
    except (TypeError, ValueError):
        return str(declared).strip().strip('"').lower()
    while isinstance(found, list) and found:
        head = str(found[0]).lower()
        if head in ("list", "set"):
            return "list"
        if head in ("map", "object"):
            return "map"
        found = found[0]
    return str(found).lower()


def _value(kind: str, number: int) -> str:
    """A placeholder shaped like the type, so the shape is right on arrival."""
    said = _shape(kind)
    if said == "list":
        return "[${N}]".replace("N", str(number))
    if said == "map":
        return "{\n    ${N}\n  }".replace("N", str(number))
    return BY_TYPE.get(said, '"${N}"').replace("N", str(number))


# Terraform's own, never a provider's. `id` in particular is declared by nearly
# every AWS resource as optional-and-computed and is not settable by anybody —
# a snippet that writes it produces a file that will not apply.
RESERVED = frozenset({"id", "count", "for_each", "provider", "lifecycle", "depends_on"})


def _is_writable(attribute) -> bool:
    """Whether this is something a person sets, or something they are told.

    A purely computed attribute is an output of the resource. AWS marks most of
    its arguments optional *and* computed, which means "set it or I will" — so
    the test is on `optional` rather than on `computed`.
    """
    if attribute.name in RESERVED:
        return False
    return bool(attribute.required or attribute.optional)


def _line(name: str, kind: str, number: int, *, width: int, note: str = "") -> str:
    """One argument. A note on a multi-line value goes on the opening line,
    where it belongs to the argument rather than trailing its closing brace."""
    padded = name.ljust(width)
    value = _value(kind, number)
    if note and "\n" in value:
        head, rest = value.split("\n", 1)
        return f"  {padded} = {head}{note}\n{rest}"
    return f"  {padded} = {value}{note}"


def for_resource(index, type_: str, *, kind: str = "resource") -> list[Entry]:
    """The short and the full entry for one resource type.

    Returns nothing when the schema has never heard of the type. An entry
    invented for an unknown resource would be a confident guess about somebody
    else's provider.
    """
    found = index.resource(type_, kind=kind) if hasattr(index, "resource") else None
    if found is None:
        return []
    attributes = [
        attribute for attribute in index.attributes(type_, kind=kind) if _is_writable(attribute)
    ]
    required = [attribute for attribute in attributes if attribute.required]
    label = "resource" if kind == "resource" else "data"

    short = _entry(
        name=f"{type_} — required only",
        type_=type_,
        label=label,
        attributes=required,
        about=(
            f"The {len(required)} argument{'' if len(required) == 1 else 's'} this resource "
            "cannot be written without."
            if required
            else "This resource has no required arguments."
        ),
        tags=("generated", "required"),
    )
    entries = [short]

    if attributes and len(attributes) != len(required) and len(attributes) <= MOST_ARGUMENTS:
        entries.append(
            _entry(
                name=f"{type_} — every argument",
                type_=type_,
                label=label,
                attributes=attributes,
                about=(
                    f"All {len(attributes)} arguments, with their types. "
                    "Optional ones are marked; delete what you do not need."
                ),
                tags=("generated", "full"),
                annotate=True,
            )
        )
    return entries


def _entry(
    *,
    name: str,
    type_: str,
    label: str,
    attributes: list,
    about: str,
    tags: tuple[str, ...],
    annotate: bool = False,
) -> Entry:
    width = max((len(a.name) for a in attributes), default=0)
    lines = []
    for number, attribute in enumerate(attributes, start=2):
        note = ""
        if annotate:
            note = f"  # {_shape(attribute.type)}" + ("" if attribute.required else ", optional")
        lines.append(_line(attribute.name, attribute.type, number, width=width, note=note))
    inside = "\n".join(lines) if lines else "  ${0}"
    body = f'{label} "{type_}" "${{1:name}}" {{\n{inside}\n}}\n'
    return Entry(
        name=name,
        kind=Kind.SNIPPET,
        body=body,
        about=about,
        tags=tags,
        source=Source.BUILT_IN,
        resource=type_,
    )


def matching(index, prefix: str = "", *, limit: int = 30) -> list[Entry]:
    """Entries for the resource types whose name starts with `prefix`.

    Asked for by prefix rather than built all at once: a real provider index
    holds thousands of types, and generating two entries for every one of them
    to show a list of ten is work nobody asked for.
    """
    found: list[Entry] = []
    for kind in ("resource", "data_source"):
        for type_ in index.resource_types(prefix, kind=kind, limit=limit):
            found.extend(for_resource(index, type_, kind=kind))
    return found
