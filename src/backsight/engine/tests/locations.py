"""Where each `run` block sits in a test file, so a result can be marked on it.

The results stream names a run and gives a line only for a *failure*. A passing
run has no location in the JSON at all, so the gutter cannot be drawn from the
results alone — the file has to be read.
"""

from __future__ import annotations

from dataclasses import dataclass

from backsight.engine.hcl.parse import blocks, body_of

RUN = "run"
ASSERT = "assert"


@dataclass(frozen=True)
class RunBlock:
    """One `run` block: its name, and the lines it starts and ends on."""

    name: str
    line: int
    last_line: int
    assertions: tuple[int, ...] = ()

    def contains(self, line: int) -> bool:
        return self.line <= line <= self.last_line


def runs(source: bytes) -> list[RunBlock]:
    """Reads every `run` block out of a `.tftest.hcl` file, in file order.

    Lines are 1-based, matching the engine's own diagnostics and the gutter.
    """
    body = body_of(source)
    found: list[RunBlock] = []
    for block in blocks(body, source, RUN):
        if not block.labels:
            # `run` without a name is a syntax error the engine will report;
            # skipping it here means the gutter is short rather than wrong.
            continue
        inner = body_of_block(block)
        assertions = tuple(
            assertion.node.start_point[0] + 1 for assertion in blocks(inner, source, ASSERT)
        )
        found.append(
            RunBlock(
                name=block.labels[0],
                line=block.node.start_point[0] + 1,
                last_line=block.node.end_point[0] + 1,
                assertions=assertions,
            )
        )
    return found


def body_of_block(block) -> object | None:
    """The body node inside a block, or None when it has none."""
    for child in block.node.children:
        if child.type == "body":
            return child
    return None


def at(source: bytes, line: int) -> RunBlock | None:
    """The run block a line falls inside, so a click in the gutter finds it."""
    for block in runs(source):
        if block.contains(line):
            return block
    return None
