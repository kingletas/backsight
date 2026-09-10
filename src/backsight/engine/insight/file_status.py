"""Everything a tab says about one file, in one place.

Four independent states on one small tab, each in its own slot, so a
file can be untracked, unsaved, focused and creating three resources and say all
of it at once without becoming a smear.

The rule that stops it lying: **plan impact is cleared on the first edit after a
plan, not dimmed.** A dimmed marker still reads as information, and a stale plan
marker is a confident lie — which is the failure this whole product exists to
avoid.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from backsight.engine.insight.source_map import SourceMap
from backsight.engine.plan.model import Action, Plan
from backsight.engine.vcs.git import Status, Vcs


class Impact(Enum):
    """What the plan will do to the resources declared in one file."""

    DESTROY = "destroy"
    REPLACE = "replace"
    CHANGE = "change"
    CREATE = "create"
    UNTOUCHED = "untouched"

    @property
    def tone(self) -> str:
        """The word the theme colours by. Destroy and replace share a colour."""
        return {
            "destroy": "destroy",
            "replace": "replace",
            "change": "change",
            "create": "add",
        }.get(self.value, "none")

    @property
    def is_thick(self) -> bool:
        """Destroy is thicker, not only redder."""
        return self is Impact.DESTROY


# Ordered by consequence, not by count. One destroy outranks nine creates.
IMPACT_PRECEDENCE = (
    Impact.DESTROY,
    Impact.REPLACE,
    Impact.CHANGE,
    Impact.CREATE,
    Impact.UNTOUCHED,
)

FROM_ACTION = {
    Action.DELETE: Impact.DESTROY,
    Action.REPLACE: Impact.REPLACE,
    Action.UPDATE: Impact.CHANGE,
    Action.CREATE: Impact.CREATE,
}


@dataclass(frozen=True)
class FileStatus:
    """One file, in every slot a tab has."""

    path: Path
    vcs: Vcs = Vcs.UNCHANGED
    impact: Impact = Impact.UNTOUCHED
    unsaved: bool = False
    unreadable: bool = False
    counts: tuple[tuple[Impact, int], ...] = ()

    @property
    def shows_impact(self) -> bool:
        """An unparseable file has no meaningful plan state.

        FR-ED-19e: unreadable outranks everything, and the bottom edge
        is suppressed rather than showing something stale.
        """
        return not self.unreadable and self.impact is not Impact.UNTOUCHED

    @property
    def summary(self) -> str:
        """`＋3 ◆1 ▲1`, the way the rail shows it.

        The same four glyphs the verdict line and the gutter use. One vocabulary
        across the product: a reader should not have to learn that `±` here and
        `▲` there are the same thing.
        """
        found = dict(self.counts)
        # Read in the order the verdict line reads them, not in the order the
        # plan happened to record them: two summaries of one plan that put the
        # same four counts in different orders are two things to learn.
        return " ".join(
            f"{glyph}{found[impact]}" for impact, glyph in GLYPHS.items() if found.get(impact)
        )


# Add, change in place, replace, destroy. Shape as well as colour, so a count
# survives a monochrome screenshot.
GLYPHS = {
    Impact.CREATE: "＋",
    Impact.CHANGE: "◆",
    Impact.REPLACE: "▲",
    Impact.DESTROY: "▼",
}


def combined(statuses: list[FileStatus]) -> str:
    """What the plan would do to a group of files, as one summary.

    A module row shows this so a collapsed module still answers whether the
    plan touches it.
    """
    total: dict[Impact, int] = {}
    for status in statuses:
        for impact, count in status.counts:
            total[impact] = total.get(impact, 0) + count
    return " ".join(f"{GLYPHS[impact]}{total[impact]}" for impact in GLYPHS if total.get(impact))


def highest(impacts: list[Impact]) -> Impact:
    """The most consequential of several, never the most numerous."""
    for candidate in IMPACT_PRECEDENCE:
        if candidate in impacts:
            return candidate
    return Impact.UNTOUCHED


def for_files(
    paths: list[Path],
    *,
    plan: Plan | None = None,
    source_map: SourceMap | None = None,
    vcs: Status | None = None,
    unsaved: set[Path] | None = None,
    unreadable: set[Path] | None = None,
) -> dict[Path, FileStatus]:
    """One status per file, from whichever sources are available.

    A missing source is an absent slot rather than a wrong one: with no plan
    every file is untouched, which is true, because no plan has said otherwise.
    """
    by_file: dict[Path, list[Impact]] = {}
    if plan is not None and source_map is not None:
        for change in plan.effective:
            place = source_map.locate(change.address)
            impact = FROM_ACTION.get(change.action)
            if place is None or impact is None:
                continue
            by_file.setdefault(place.path.resolve(), []).append(impact)

    unsaved = {p.resolve() for p in (unsaved or set())}
    unreadable = {p.resolve() for p in (unreadable or set())}

    found: dict[Path, FileStatus] = {}
    for path in paths:
        resolved = Path(path).resolve()
        impacts = by_file.get(resolved, [])
        tally = Counter(impacts)
        found[resolved] = FileStatus(
            path=resolved,
            vcs=vcs.of(resolved) if vcs else Vcs.UNCHANGED,
            impact=highest(impacts),
            unsaved=resolved in unsaved,
            unreadable=resolved in unreadable,
            counts=tuple(
                (impact, tally[impact]) for impact in IMPACT_PRECEDENCE if tally.get(impact)
            ),
        )
    return found


def cleared_of_plan(statuses: dict[Path, FileStatus]) -> dict[Path, FileStatus]:
    """After the first edit following a plan.

    Cleared rather than dimmed. A dimmed marker still reads as information, and
    the information is no longer true.
    """
    return {
        path: FileStatus(
            path=status.path,
            vcs=status.vcs,
            impact=Impact.UNTOUCHED,
            unsaved=status.unsaved,
            unreadable=status.unreadable,
            counts=(),
        )
        for path, status in statuses.items()
    }
