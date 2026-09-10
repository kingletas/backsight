"""Changes to a file, expressed as byte ranges rather than as new content.

An edit names a span and what replaces it. Applying edits to the original bytes
leaves everything outside those spans untouched — not because care was taken,
but because nothing else is ever written. That is what makes FR-ED-07 hold
through a refactor rather than only through an open-and-save.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Edit:
    """Replace `[start, end)` in one file with this text."""

    path: Path
    start: int
    end: int
    replacement: str
    reason: str = ""

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"an edit needs a forward span, got {self.start}..{self.end}")


def apply_to(data: bytes, edits: list[Edit]) -> bytes:
    """Applies edits to one file's bytes, last first so offsets stay valid."""
    overlapping = _overlap(edits)
    if overlapping is not None:
        # Two edits over the same bytes means the analysis found the same thing
        # twice or found two different things in one place. Either way the result
        # would depend on ordering, which is not something to leave to chance.
        raise ValueError(f"two edits overlap at {overlapping}")
    out = data
    for edit in sorted(edits, key=lambda e: e.start, reverse=True):
        out = out[: edit.start] + edit.replacement.encode("utf-8") + out[edit.end :]
    return out


def _overlap(edits: list[Edit]) -> tuple[int, int] | None:
    ordered = sorted(edits, key=lambda e: (e.start, e.end))
    for earlier, later in zip(ordered, ordered[1:], strict=False):
        if later.start < earlier.end:
            return (later.start, earlier.end)
    return None


def group(edits: list[Edit]) -> dict[Path, list[Edit]]:
    by_file: dict[Path, list[Edit]] = {}
    for edit in edits:
        by_file.setdefault(edit.path, []).append(edit)
    return by_file
