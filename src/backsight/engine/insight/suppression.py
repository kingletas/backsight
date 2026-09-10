"""Findings somebody has decided not to see, and when that decision expires.

**Every suppression has an expiry.** A permanent one is how a finding stops
being a decision and becomes a fact of the codebase that nobody remembers
agreeing to. The menu says "Suppress with expiry…" for that reason, and there
is no way to suppress without one.

The file is committed with the workspace: a suppression is a team decision
about a specific risk, and one that lived only on somebody's laptop would be
invisible to everybody reviewing the same code.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

FILE = "suppressions.toml"
DIRECTORY = ".backsight"

# What a suppression may last. Beyond this it is not a deferral any more.
LONGEST = timedelta(days=365)


@dataclass(frozen=True)
class Suppression:
    """One finding, hidden until a date, with the reason it was hidden."""

    address: str
    finding: str
    until: date
    reason: str = ""

    def is_active(self, on: date) -> bool:
        return on <= self.until

    def __str__(self) -> str:
        said = f"{self.finding} on {self.address} until {self.until.isoformat()}"
        return f"{said} — {self.reason}" if self.reason else said


@dataclass
class Suppressions:
    """Everything suppressed in one workspace."""

    entries: list[Suppression] = field(default_factory=list)
    path: Path | None = None

    def active(self, on: date) -> list[Suppression]:
        return [entry for entry in self.entries if entry.is_active(on)]

    def expired(self, on: date) -> list[Suppression]:
        """Suppressions whose date has passed. They stop hiding anything."""
        return [entry for entry in self.entries if not entry.is_active(on)]

    def hides(self, address: str, finding: str, on: date) -> bool:
        return any(
            entry.address == address and entry.finding == finding for entry in self.active(on)
        )


def location(workspace: Path) -> Path:
    return Path(workspace) / DIRECTORY / FILE


def read(workspace: Path) -> Suppressions:
    """Reads the file, or reports a workspace that suppresses nothing."""
    path = location(workspace)
    if not path.is_file():
        return Suppressions()
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        # An unreadable file must not hide findings by accident: the safe
        # failure is to suppress nothing.
        return Suppressions(path=path)
    entries: list[Suppression] = []
    for entry in document.get("suppress") or []:
        parsed = _entry(entry)
        if parsed is not None:
            entries.append(parsed)
    return Suppressions(entries=entries, path=path)


def add(workspace: Path, suppression: Suppression, *, on: date) -> Path:
    """Appends a suppression, refusing one that lasts too long or not at all."""
    if suppression.until <= on:
        raise ValueError("a suppression that has already expired hides nothing")
    if suppression.until - on > LONGEST:
        raise ValueError(
            f"a suppression may last at most {LONGEST.days} days; beyond that it is not a deferral"
        )
    path = location(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else _header()
    path.write_text(existing + _rendered(suppression), encoding="utf-8")
    return path


def _header() -> str:
    return (
        "# Findings suppressed in this workspace, and when each decision runs out.\n"
        "# Committed on purpose: a suppression is a decision about a real risk,\n"
        "# and one that lived on a laptop would be invisible to a reviewer.\n"
    )


def _rendered(suppression: Suppression) -> str:
    reason = suppression.reason.replace('"', '\\"')
    return (
        "\n[[suppress]]\n"
        f'address = "{suppression.address}"\n'
        f'finding = "{suppression.finding}"\n'
        f"until   = {suppression.until.isoformat()}\n"
        f'reason  = "{reason}"\n'
    )


def _entry(entry: object) -> Suppression | None:
    if not isinstance(entry, dict):
        return None
    until = entry.get("until")
    if isinstance(until, str):
        try:
            until = date.fromisoformat(until)
        except ValueError:
            return None
    if not isinstance(until, date):
        # No expiry means no suppression. A missing date is not "forever".
        return None
    address = str(entry.get("address", ""))
    finding = str(entry.get("finding", ""))
    if not address or not finding:
        return None
    return Suppression(
        address=address, finding=finding, until=until, reason=str(entry.get("reason", ""))
    )
