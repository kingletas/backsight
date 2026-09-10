"""Resolved values and expansion, on the line that declares them.

The inlay hints, which are BRD §6.13 — FR-DBG-02 and FR-DBG-03. All of
it comes from the plan Backsight already holds, so a `for_each` surprise is
answered before planning rather than after applying.

Off by default, like everything in the annotations list. Somebody will
find each layer noisy and should be able to turn off exactly the one that
bothers them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backsight.engine.hcl import parse
from backsight.engine.insight.expressions import expansion, resolved
from backsight.engine.insight.source_map import SourceMap

# Only these carry a hint. Hinting every attribute would bury the two that
# matter under a screen of noise.
#
# In a plan's configuration section these are **not** inside `expressions`; they
# are top-level keys on the resource, named `count_expression` and
# `for_each_expression`. Looking for them under `expressions` finds nothing and
# produces no hints at all, silently.
EXPANDERS = {"for_each": "for_each_expression", "count": "count_expression"}


@dataclass(frozen=True)
class Hint:
    """One line, and what the plan says about it."""

    path: Path
    line: int
    text: str
    tone: str = "hint"


def for_plan(document: dict[str, Any], source_map: SourceMap) -> list[Hint]:
    """A hint per expanding resource, on the line that expands it."""
    found: list[Hint] = []
    for entry in (document.get("configuration") or {}).get("root_module", {}).get("resources", []):
        address = entry.get("address", "")
        place = source_map.locate(address)
        if place is None:
            continue
        for attribute, key in EXPANDERS.items():
            if key not in entry:
                continue
            line = _line_of(place.path, place.line, attribute)
            if line is None:
                continue
            spread = expansion(document, address)
            if spread.instances:
                found.append(Hint(path=place.path, line=line, text=spread.summary()))
    return sorted(found, key=lambda hint: (str(hint.path), hint.line))


def for_attribute(
    document: dict[str, Any], source_map: SourceMap, address: str, attribute: str
) -> Hint | None:
    """What one attribute resolved to, for a hover.

    Sensitive values never come back with a value — the refusal is in the type,
    not in this function remembering to ask.
    """
    place = source_map.locate(address)
    found = resolved(document, address, attribute)
    if place is None or found is None:
        return None
    line = _line_of(place.path, place.line, attribute)
    if line is None:
        return None
    return Hint(path=place.path, line=line, text=f"{attribute} → {found.display}")


def in_file(hints: list[Hint], path: Path) -> list[Hint]:
    resolved_path = Path(path).resolve()
    return [hint for hint in hints if hint.path.resolve() == resolved_path]


def _line_of(path: Path, block_line: int, attribute: str) -> int | None:
    try:
        source = path.read_bytes()
    except OSError:
        return None
    body = parse.body_of(source)
    for block in parse.blocks(body, source):
        if block.node.start_point[0] + 1 != block_line:
            continue
        return _find(block, attribute)
    return None


def _find(block: parse.Block, attribute: str) -> int | None:
    body = block.body
    if body is None:
        return None
    for child in body.children:
        if child.type != "attribute":
            continue
        identifier = next((c for c in child.children if c.type == "identifier"), None)
        if identifier is not None and parse.text(identifier, block.source) == attribute:
            return child.start_point[0] + 1
    return None
