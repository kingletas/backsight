"""Where the block around the cursor starts and ends, and what a name refers to.

All of it reads the syntax tree rather than matching text, so a brace inside a
string or a heredoc never moves the cursor somewhere absurd.
"""

from __future__ import annotations

from dataclasses import dataclass

from backsight.engine.hcl import parse


@dataclass(frozen=True)
class Block:
    """One block, by the lines it spans. 1-based, as a person counts."""

    first: int
    last: int
    type: str = ""
    labels: tuple[str, ...] = ()

    @property
    def address(self) -> str:
        """The address a plan would use, or an empty string for blocks with none."""
        if self.type == "resource" and len(self.labels) >= 2:
            return f"{self.labels[0]}.{self.labels[1]}"
        if self.type == "data" and len(self.labels) >= 2:
            return f"data.{self.labels[0]}.{self.labels[1]}"
        if self.type in ("variable", "output", "local", "module") and self.labels:
            return f"{self.type}.{self.labels[0]}"
        return ""

    def contains(self, line: int) -> bool:
        return self.first <= line <= self.last


def blocks(source: bytes) -> list[Block]:
    """Every top-level block, in file order."""
    body = parse.body_of(source)
    if body is None:
        return []
    found: list[Block] = []
    for block in parse.blocks(body, source):
        found.append(
            Block(
                first=block.node.start_point[0] + 1,
                last=block.node.end_point[0] + 1,
                type=block.type,
                labels=block.labels,
            )
        )
    return sorted(found, key=lambda one: one.first)


def enclosing(source: bytes, line: int) -> Block | None:
    """The innermost block a line sits in, or None between blocks."""
    found = [block for block in blocks(source) if block.contains(line)]
    if not found:
        return None
    return min(found, key=lambda block: block.last - block.first)


def start_of(source: bytes, line: int) -> int | None:
    """Where the enclosing block begins, or the previous block when between."""
    here = enclosing(source, line)
    if here is not None and here.first != line:
        return here.first
    earlier = [block for block in blocks(source) if block.last < line]
    return earlier[-1].first if earlier else None


def end_of(source: bytes, line: int) -> int | None:
    """Where the enclosing block ends, or the next block when between."""
    here = enclosing(source, line)
    if here is not None and here.last != line:
        return here.last
    later = [block for block in blocks(source) if block.first > line]
    return later[0].last if later else None


def declaring(source: bytes, address: str) -> Block | None:
    """The block that declares an address, for go-to-definition."""
    for block in blocks(source):
        if block.address and block.address == address:
            return block
    return None


def references_in(source: bytes, address: str) -> list[int]:
    """Every line mentioning an address, excluding its own declaration.

    A reference is found in expression text rather than by resolving scope, so
    a name inside a comment or a string counts. That is a deliberate floor:
    over-reporting a place to look is recoverable, and missing the one line
    that matters is not.
    """
    declaration = declaring(source, address)
    found: list[int] = []
    for number, line in enumerate(source.decode("utf-8", "replace").splitlines(), start=1):
        if address not in line:
            continue
        if declaration is not None and number == declaration.first:
            continue
        found.append(number)
    return found
