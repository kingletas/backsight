"""Where in the files a resource the plan mentions was actually written.

FR-ED-05: a finding the author cannot locate is a finding they will not fix. The
plan talks in addresses like `module.vpc.aws_subnet.this[0]`; a person needs a
file and a line.

Built from the syntax tree rather than by searching for the text, because a
resource address appears in comments, in strings and in `depends_on` lists, and
only one of those occurrences is the declaration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from backsight.engine.hcl import parse
from backsight.engine.workspace.discovery import Module, Workspace

# `aws_subnet.this[0]` and `aws_subnet.this["a"]` are both `aws_subnet.this`.
INDEX = re.compile(r"\[[^\]]*\]")


@dataclass(frozen=True)
class Location:
    """A place in a file, counted the way an editor counts."""

    path: Path
    line: int
    column: int = 0
    # The last line of the block, so an annotation can be drawn as the region
    # it is about rather than as a glyph repeated down it. Zero means the
    # extent was never read, which is not the same as a one-line block.
    last_line: int = 0

    def __str__(self) -> str:
        return f"{self.path.name}:{self.line}"

    @property
    def lines(self) -> range:
        """Every line the block occupies, counted the way an editor counts."""
        return range(self.line, max(self.line, self.last_line) + 1)


@dataclass
class SourceMap:
    """Addresses to the place they were declared, for one root module and its children."""

    places: dict[str, Location] = field(default_factory=dict)

    def locate(self, address: str) -> Location | None:
        """The declaration for a plan address, indices and instances removed."""
        return self.places.get(INDEX.sub("", address))

    @classmethod
    def build(cls, workspace: Workspace, root: Module) -> SourceMap:
        found = cls()
        found._read(workspace, root, prefix="")
        return found

    def _read(self, workspace: Workspace, module: Module, prefix: str, depth: int = 0) -> None:
        # A module that calls itself, directly or through a chain, would other-
        # wise be walked until the stack runs out.
        if depth > 16:
            return
        for path in module.files:
            if path.suffix != ".tf":
                continue
            source = path.read_bytes()
            for block in parse.blocks(parse.body_of(source), source):
                address = _address_of(block)
                if address is None:
                    continue
                # The block's own line, one-based, as an editor counts.
                line = block.node.start_point[0] + 1
                column = block.node.start_point[1]
                self.places[f"{prefix}{address}"] = Location(
                    path=path, line=line, column=column, last_line=block.node.end_point[0] + 1
                )

        for call in module.calls:
            target = call.target()
            if target is None:
                continue
            child = workspace.module_at(target)
            if child is None:
                continue
            self._read(workspace, child, prefix=f"{prefix}module.{call.name}.", depth=depth + 1)


def _address_of(block: parse.Block) -> str | None:
    """The address a plan would use for this block, or nothing for blocks with none."""
    if block.type == "resource" and len(block.labels) >= 2:
        return f"{block.labels[0]}.{block.labels[1]}"
    if block.type == "data" and len(block.labels) >= 2:
        return f"data.{block.labels[0]}.{block.labels[1]}"
    if block.type == "module" and block.labels:
        return f"module.{block.labels[0]}"
    return None


def attribute_line(source: bytes, address_line: int, attribute: str) -> int | None:
    """The line an attribute sits on inside the block starting at `address_line`.

    Used to hang a verdict off the argument that caused it rather than off the
    top of the resource, which is the difference between a finding somebody can
    act on and one they have to hunt for.
    """
    body = parse.body_of(source)
    for block in parse.blocks(body, source):
        if block.node.start_point[0] + 1 != address_line:
            continue
        return _find_attribute(block, attribute)
    return None


def _find_attribute(block: parse.Block, attribute: str) -> int | None:
    body = block.body
    if body is None:
        return None
    for child in body.children:
        if child.type != "attribute":
            continue
        identifier = next((c for c in child.children if c.type == "identifier"), None)
        if identifier is None:
            continue
        if parse.text(identifier, block.source) == attribute:
            return child.start_point[0] + 1
    for nested in parse.blocks(body, block.source):
        found = _find_attribute(nested, attribute)
        if found is not None:
            return found
    return None
