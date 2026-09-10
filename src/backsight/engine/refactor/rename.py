"""Renaming a resource, through the syntax tree.

FR-REF-01. Text substitution gets this wrong in ways that are hard to see: the
old name appears in comments, in strings, in a tag value and in an unrelated
resource of a different type that happens to share it. Only one occurrence is
the declaration and only some of the rest are references.

This produces edits and a `moved` block. It does not decide whether the result
is safe — that is the verification gate, and nothing here should be applied
without it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backsight.engine.hcl import parse
from backsight.engine.refactor.edits import Edit

# Blocks whose second label is the name being renamed.
ADDRESSABLE = ("resource", "data")


@dataclass(frozen=True)
class Rename:
    """One resource, and what it should be called."""

    resource_type: str
    old_name: str
    new_name: str
    kind: str = "resource"

    def __post_init__(self) -> None:
        if not self.new_name:
            raise ValueError("a rename needs a new name")
        if self.old_name == self.new_name:
            raise ValueError("the new name is the old name")

    @property
    def prefix(self) -> str:
        return "" if self.kind == "resource" else "data."

    @property
    def old_address(self) -> str:
        return f"{self.prefix}{self.resource_type}.{self.old_name}"

    @property
    def new_address(self) -> str:
        return f"{self.prefix}{self.resource_type}.{self.new_name}"


def moved_block(rename: Rename) -> str:
    """The block that tells the state the address changed.

    Written out rather than described, because FR-REF-01's whole point is that
    the user can read what was generated and disagree with it.
    """
    return f"\nmoved {{\n  from = {rename.old_address}\n  to   = {rename.new_address}\n}}\n"


def edits_for(files: dict[Path, bytes], rename: Rename) -> list[Edit]:
    """Every span that has to change, across every file given."""
    found: list[Edit] = []
    for path, source in files.items():
        found.extend(_declaration(path, source, rename))
        found.extend(_references(path, source, rename))
    return sorted(found, key=lambda e: (str(e.path), e.start))


def declaration_count(files: dict[Path, bytes], rename: Rename) -> int:
    """How many blocks claim this address. Anything but one is a refusal."""
    return sum(len(_declaration(path, source, rename)) for path, source in files.items())


def _declaration(path: Path, source: bytes, rename: Rename) -> list[Edit]:
    found = []
    for block in parse.blocks(parse.body_of(source), source):
        if block.type not in ADDRESSABLE or block.type != rename.kind:
            continue
        if len(block.labels) < 2:
            continue
        if block.labels[0] != rename.resource_type or block.labels[1] != rename.old_name:
            continue
        labels = [c for c in block.node.children if c.type == "string_lit"]
        literal = next((c for c in labels[1].children if c.type == "template_literal"), None)
        if literal is None:
            continue
        found.append(
            Edit(
                path=path,
                start=literal.start_byte,
                end=literal.end_byte,
                replacement=rename.new_name,
                reason="the declaration",
            )
        )
    return found


def _references(path: Path, source: bytes, rename: Rename) -> list[Edit]:
    """Every `type.name` used as an expression, and nothing that only looks like one."""
    found: list[Edit] = []
    root = parse.parse(source)
    _walk_references(root, source, path, rename, found)
    return found


def _walk_references(node, source: bytes, path: Path, rename: Rename, found: list[Edit]) -> None:
    if node.type == "expression":
        edit = _reference_in(node, source, path, rename)
        if edit is not None:
            found.append(edit)
    for child in node.children:
        _walk_references(child, source, path, rename, found)


def _reference_in(expression, source: bytes, path: Path, rename: Rename) -> Edit | None:
    """A reference is `variable_expr` followed by `get_attr` siblings.

    For a data source the chain starts with `data`, so the type and the name sit
    one step further along.
    """
    children = list(expression.children)
    if not children or children[0].type != "variable_expr":
        return None
    head = next((c for c in children[0].children if c.type == "identifier"), None)
    if head is None:
        return None

    parts = [head]
    for child in children[1:]:
        if child.type != "get_attr":
            break
        identifier = next((c for c in child.children if c.type == "identifier"), None)
        if identifier is None:
            break
        parts.append(identifier)

    wanted = (
        ["data", rename.resource_type, rename.old_name]
        if rename.kind == "data"
        else [
            rename.resource_type,
            rename.old_name,
        ]
    )
    if len(parts) < len(wanted):
        return None
    if [parse.text(p, source) for p in parts[: len(wanted)]] != wanted:
        return None

    name_node = parts[len(wanted) - 1]
    return Edit(
        path=path,
        start=name_node.start_byte,
        end=name_node.end_byte,
        replacement=rename.new_name,
        reason="a reference",
    )
