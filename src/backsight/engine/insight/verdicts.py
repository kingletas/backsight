"""What the plan says, attached to the lines that caused it.

FR-ED-05. A verdict on the first line of a resource is one the author has to
hunt through the block for, so a replacement hangs off the argument the plan
blames rather than off the block it belongs to.

Kept engine-side so the mapping can be checked without a window, and so a second
front end cannot anchor the same finding somewhere else.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backsight.engine.insight.source_map import SourceMap, attribute_line
from backsight.engine.plan.model import Action, Plan
from backsight.engine.presentation import language


@dataclass(frozen=True)
class Verdict:
    """One thing to say, and exactly where to say it."""

    path: Path
    line: int
    text: str
    tone: str
    address: str = ""
    # The block this verdict is about, first and last line. The mark hangs off
    # `line` — which for a replacement is the argument the plan blames — and
    # the spine is drawn down the whole block, because what the plan will do is
    # a fact about the region rather than about one row of it.
    first_line: int = 0
    last_line: int = 0

    @property
    def is_warning(self) -> bool:
        return self.tone in ("destroy", "replace")

    @property
    def block(self) -> range:
        """Every line of the block, or just this one when the extent is unknown."""
        if not self.first_line or self.last_line < self.first_line:
            return range(self.line, self.line + 1)
        return range(self.first_line, self.last_line + 1)


def for_plan(plan: Plan, source_map: SourceMap) -> list[Verdict]:
    """A verdict per changed resource, on the best line available for it.

    A change whose declaration is not in these files gets no verdict rather than
    one on a guessed line. Silence is recoverable; a marker on the wrong line
    sends somebody to edit the wrong thing.
    """
    found: list[Verdict] = []
    for change in plan.effective:
        place = source_map.locate(change.address)
        if place is None:
            continue
        label, _mark, tone = language.ACTIONS[change.action.value]
        line = place.line
        text = label

        if change.action is Action.REPLACE:
            causes = change.replacing_attributes
            if causes:
                text = f"Forces replacement — {', '.join(causes)}"
                on_argument = _line_of(place.path, place.line, causes[0])
                if on_argument is not None:
                    line = on_argument
            else:
                text = "Replaced; the plan does not say which attribute caused it"
        elif change.action is Action.DELETE:
            text = "Destroyed by this change"

        found.append(
            Verdict(
                path=place.path,
                line=line,
                text=text,
                tone=tone,
                address=change.address,
                first_line=place.line,
                last_line=place.last_line,
            )
        )
    return sorted(found, key=lambda v: (str(v.path), v.line))


def in_file(verdicts: list[Verdict], path: Path) -> list[Verdict]:
    """The verdicts for one open file."""
    resolved = Path(path).resolve()
    return [v for v in verdicts if v.path.resolve() == resolved]


def _line_of(path: Path, block_line: int, attribute: str) -> int | None:
    try:
        return attribute_line(path.read_bytes(), block_line, attribute)
    except OSError:
        # The file moved between planning and rendering. The block line still
        # points somewhere sensible, so fall back to it rather than dropping the
        # verdict entirely.
        return None
