"""Which tabs a close command would take, and what that would cost.

The reference menu carries ten close variants at the top level because
it lists every combination of scope and unsaved-handling. **Scope and filter are
two axes**, and multiplying them out is what produces a wall with plain "Close"
buried in it.

The rule underneath, which is worth more than the menu: *two menu items that
differ only by whether they silently destroy work should never both exist.* If a
decision has consequences, ask it once, at the moment it matters, with the
damage named.

So the counts live here — `Close others · 2 unsaved` in the menu means the
dialog is rarely a surprise, and no dialog appears at all when nothing is lost.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Scope(Enum):
    """Which tabs a close reaches."""

    THIS = "this one"
    OTHERS = "others"
    LEFT = "to the left"
    RIGHT = "to the right"
    ALL = "all"


class Filter(Enum):
    """Which of those it keeps."""

    EVERYTHING = "everything"
    SAVED_ONLY = "saved only"
    GONE_FROM_DISK = "files gone from disk"
    NOT_IN_PLAN = "not touched by the plan"


class SortOrder(Enum):
    """How the strip is ordered."""

    MANUAL = "manual"
    NAME = "name"
    PATH = "path"
    RECENT = "recently used"
    # Only possible because the plan is already in memory. The files with the
    # most planned changes come first.
    PLAN_IMPACT = "plan impact"


@dataclass(frozen=True)
class OpenTab:
    """One open file, as far as the tab strip is concerned."""

    path: Path
    unsaved: bool = False
    on_disk: bool = True
    touched_by_plan: bool = False
    changed_lines: int = 0
    used_at: float = 0.0
    plan_changes: int = 0
    preview: bool = False
    pinned: bool = False


@dataclass(frozen=True)
class Selection:
    """What a close command would take, and what it would cost."""

    tabs: tuple[OpenTab, ...]
    scope: Scope
    filter: Filter = Filter.EVERYTHING

    @property
    def count(self) -> int:
        return len(self.tabs)

    @property
    def unsaved(self) -> tuple[OpenTab, ...]:
        return tuple(tab for tab in self.tabs if tab.unsaved)

    @property
    def costs_work(self) -> bool:
        """Whether a dialog is warranted at all.

        Confirmation for a harmless action teaches people to click through
        confirmations, which is how the harmful one gets clicked through too.
        """
        return bool(self.unsaved)

    def label(self) -> str:
        """`5 · 1 unsaved`, put on the menu item before anything is clicked."""
        if not self.count:
            return "none"
        said = str(self.count)
        if self.unsaved:
            said += f" · {len(self.unsaved)} unsaved"
        return said


def select(
    tabs: list[OpenTab],
    active: int,
    scope: Scope,
    keep: Filter = Filter.EVERYTHING,
) -> Selection:
    """The tabs a close would take. Pinned tabs are never taken."""
    chosen: list[OpenTab] = []
    for index, tab in enumerate(tabs):
        if tab.pinned:
            continue
        if scope is Scope.OTHERS and index == active:
            continue
        if scope is Scope.LEFT and index >= active:
            continue
        if scope is Scope.RIGHT and index <= active:
            continue
        if not _passes(tab, keep):
            continue
        chosen.append(tab)
    return Selection(tabs=tuple(chosen), scope=scope, filter=keep)


def _passes(tab: OpenTab, keep: Filter) -> bool:
    if keep is Filter.SAVED_ONLY:
        return not tab.unsaved
    if keep is Filter.GONE_FROM_DISK:
        return not tab.on_disk
    if keep is Filter.NOT_IN_PLAN:
        return not tab.touched_by_plan
    return True


def damage(selection: Selection) -> list[str]:
    """What would be lost, named file by file.

    Fourteen changed lines is a decision; "unsaved changes" is a shrug.
    """
    return [
        f"{tab.path.name} — {tab.changed_lines} line{'' if tab.changed_lines == 1 else 's'} changed"
        if tab.changed_lines
        else f"{tab.path.name} — unsaved"
        for tab in selection.unsaved
    ]


def changed_lines(before: str, after: str) -> int:
    """How many lines differ, for the dialog to name."""
    was, now = before.split("\n"), after.split("\n")
    common_head = 0
    while common_head < min(len(was), len(now)) and was[common_head] == now[common_head]:
        common_head += 1
    common_tail = 0
    while (
        common_tail < min(len(was), len(now)) - common_head
        and was[-1 - common_tail] == now[-1 - common_tail]
    ):
        common_tail += 1
    return max(len(was), len(now)) - common_head - common_tail


def sort_tabs(tabs: list[OpenTab], order: SortOrder) -> list[OpenTab]:
    """Reorders the strip. Manual leaves it exactly as it is."""
    if order is SortOrder.MANUAL:
        return list(tabs)
    if order is SortOrder.NAME:
        return sorted(tabs, key=lambda t: t.path.name.casefold())
    if order is SortOrder.PATH:
        return sorted(tabs, key=lambda t: str(t.path).casefold())
    if order is SortOrder.RECENT:
        return sorted(tabs, key=lambda t: t.used_at, reverse=True)
    # Most planned changes first — the files a review should start with.
    return sorted(tabs, key=lambda t: (-t.plan_changes, t.path.name.casefold()))
