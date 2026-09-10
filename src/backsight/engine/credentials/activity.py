"""What this application has done, kept so it can be read back later.

FR-SEC-08. "What did I change last Tuesday" is asked constantly and answered
badly, usually by reading a terminal's scrollback until it runs out. This keeps
the plans, applies, drift checks and refactors with their timestamps, on this
machine only, and hands them over as a file when somebody wants one.

**Nothing sensitive is written.** An entry is what happened and where, never a
credential, never a variable value, never the contents of a plan. The engine
redacts sensitive values on its own and this must not become the copy that does
not — so it records the shape of what ran, and the plan itself stays where it
already is.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

FILE = "activity.jsonl"

# Enough to answer "what happened this month" and small enough to read.
MOST = 2000


class What(Enum):
    """The kinds of thing worth being able to look up afterwards."""

    PLANNED = "planned"
    APPLIED = "applied"
    DRIFT = "checked for drift"
    REFACTORED = "refactored"
    TESTED = "ran tests"
    FORMATTED = "formatted"


@dataclass(frozen=True)
class Happened:
    """One thing that happened, and enough about it to recognise it later."""

    what: What
    workspace: str = ""
    # Which declared stack this was, when the module it ran on belongs to one.
    # Empty for a module nobody has grouped, which is most of them.
    stack: str = ""
    detail: str = ""
    outcome: str = ""
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    @property
    def line(self) -> str:
        """One line, the way somebody scanning a month would want it."""
        when = self.at.replace("T", " ").replace("+00:00", "")
        said = [when, self.what.value]
        if self.workspace:
            said.append(Path(self.workspace).name)
        if self.detail:
            said.append(self.detail)
        if self.outcome:
            said.append(f"— {self.outcome}")
        return " · ".join(said[:3]) + (f" · {' '.join(said[3:])}" if said[3:] else "")


def directory(home: Path | None = None) -> Path:
    if home is not None:
        return Path(home) / ".local" / "state" / "backsight"
    root = os.environ.get("XDG_STATE_HOME")
    base = Path(root) if root else Path.home() / ".local" / "state"
    return base / "backsight"


def record(entry: Happened, *, home: Path | None = None) -> None:
    """Appends one line. A failure to write is never a failure of the work."""
    where = directory(home)
    try:
        where.mkdir(parents=True, exist_ok=True)
        with (where / FILE).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**asdict(entry), "what": entry.what.value}) + "\n")
    except OSError:
        # Losing a log line must never lose an apply. Said nowhere because
        # there is nothing a person would do about it mid-apply.
        return


def read(*, home: Path | None = None, limit: int = MOST) -> list[Happened]:
    """What is on record, newest last, skipping anything unreadable."""
    path = directory(home) / FILE
    found: list[Happened] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return found
    for line in lines[-limit:]:
        try:
            stored = json.loads(line)
            found.append(
                Happened(
                    what=What(stored["what"]),
                    workspace=str(stored.get("workspace", "")),
                    stack=str(stored.get("stack", "")),
                    detail=str(stored.get("detail", "")),
                    outcome=str(stored.get("outcome", "")),
                    at=str(stored.get("at", "")),
                )
            )
        except (ValueError, KeyError):
            continue
    return found


def as_text(entries: list[Happened]) -> str:
    """What gets exported. Plain lines, because they are read by a person."""
    return "\n".join(entry.line for entry in entries) + ("\n" if entries else "")


def forget(*, home: Path | None = None) -> None:
    """Deletes the log. It is somebody's record of their own work."""
    path = directory(home) / FILE
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return
