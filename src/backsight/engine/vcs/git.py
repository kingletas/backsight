"""What git thinks of each file in a workspace.

The design puts this on the left edge of every tab. The hazard it names is
staleness rather than accuracy: git status changes underneath the application on
every branch switch, rebase or external edit, and **an indicator showing last
minute's truth is worse than none, because it is trusted.**

So this recomputes rather than clears. A refresh that fails leaves the previous
answer in place and says it is stale; it never blanks the tabs, because a file
with no marker reads as unchanged, which is a claim rather than an absence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from backsight.engine.runner import process

TIMEOUT = 15.0


class Vcs(Enum):
    """What git says about one file, most consequential first."""

    CONFLICTED = "conflicted"
    DELETED = "deleted"
    MODIFIED = "modified"
    UNTRACKED = "untracked"
    UNCHANGED = "unchanged"

    @property
    def letter(self) -> str:
        """For anyone who cannot rely on hue. A setting, not a hidden flag."""
        return {"conflicted": "C", "deleted": "D", "modified": "M", "untracked": "U"}.get(
            self.value, ""
        )


# Conflict is the one that blocks work, so it wins.
PRECEDENCE = (Vcs.CONFLICTED, Vcs.DELETED, Vcs.MODIFIED, Vcs.UNTRACKED, Vcs.UNCHANGED)

# `git status --porcelain` two-character codes. Conflict is any of the pairs
# where both sides changed, which is what `U` in either column means.
CONFLICT_CODES = {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}


@dataclass
class Status:
    """Every file git has an opinion about, and when it was asked."""

    files: dict[Path, Vcs] = field(default_factory=dict)
    branch: str | None = None
    stale: bool = False
    available: bool = True

    def of(self, path: Path) -> Vcs:
        """Unchanged is the answer for anything git did not mention."""
        return self.files.get(Path(path).resolve(), Vcs.UNCHANGED)

    def tracks(self, path: Path) -> bool:
        """Whether git history exists for this file.

        With no repository the answer is no, so the git section of a menu is
        absent rather than offering a blame that cannot run.
        """
        if not self.available:
            return False
        return self.of(path) is not Vcs.UNTRACKED


def _classify(code: str) -> Vcs:
    code = code[:2]
    if code == "??":
        return Vcs.UNTRACKED
    if code in CONFLICT_CODES:
        return Vcs.CONFLICTED
    if "D" in code:
        return Vcs.DELETED
    if code.strip():
        return Vcs.MODIFIED
    return Vcs.UNCHANGED


def read(directory: Path, *, previous: Status | None = None) -> Status:
    """Asks git. On failure the previous answer is kept and marked stale.

    Clearing would make every tab read as unchanged, which is a statement rather
    than an absence of one.
    """
    try:
        result = process.start(
            ["git", "status", "--porcelain=v1", "--branch", "-z"],
            cwd=directory,
            timeout=TIMEOUT,
        ).wait(TIMEOUT + 5)
    except OSError:
        # The directory went away — a branch switch that removed it, or a
        # workspace deleted underneath us. Same handling as a failed run.
        result = None

    if result is None or not result.ok:
        if previous is not None:
            return Status(
                files=dict(previous.files),
                branch=previous.branch,
                stale=True,
                available=previous.available,
            )
        # Not a repository is an ordinary state, not a failure to report.
        return Status(available=False)

    files: dict[Path, Vcs] = {}
    branch = None
    entries = [entry for entry in result.output.split("\0") if entry]
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if entry.startswith("##"):
            branch = entry[2:].strip().split("...")[0].strip()
            continue
        if len(entry) < 4:
            continue
        code, name = entry[:2], entry[3:]
        files[(Path(directory) / name).resolve()] = _classify(code)
        if code[0] == "R":
            # A rename carries its source as the next record.
            index += 1
    return Status(files=files, branch=branch)
