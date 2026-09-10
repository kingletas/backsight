"""Unsaved work, kept somewhere it survives the process dying.

An editor that loses an hour of typing to a crash is not one anybody trusts
with the next hour. Every modified buffer is written aside as it is edited, and
what is found on the next launch is offered back.

**The original file is never touched.** Recovery writes only into its own state
directory, and restoring is somebody choosing to — a crash must not be able to
overwrite a file that was fine on disk.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

FOLDER = "recovery"


@dataclass(frozen=True)
class Unsaved:
    """One buffer that was being edited when everything stopped."""

    path: Path
    text: str
    when: datetime

    def says(self) -> str:
        return f"{self.path.name} — unsaved changes from {self.when:%-d %B at %H:%M}"


def directory(home: Path | None = None) -> Path:
    if home is not None:
        base = Path(home) / ".local" / "state"
    else:
        root = os.environ.get("XDG_STATE_HOME")
        base = Path(root) if root else Path.home() / ".local" / "state"
    return base / "backsight" / FOLDER


def keep(path: Path, text: str, home: Path | None = None) -> None:
    """Sets aside the current text of one buffer, replacing what was there."""
    where = directory(home)
    try:
        where.mkdir(parents=True, exist_ok=True)
        beside = where / f"{_name(path)}.writing"
        beside.write_text(
            json.dumps({"path": str(path), "text": text, "when": _now().isoformat()}),
            encoding="utf-8",
        )
        os.replace(beside, where / f"{_name(path)}.json")
    except OSError:
        # Best effort by design. Failing to keep a copy must not stop typing.
        return


def drop(path: Path, home: Path | None = None) -> None:
    """Forgets one buffer, because it has been saved or deliberately closed."""
    (directory(home) / f"{_name(path)}.json").unlink(missing_ok=True)


def drop_everything(home: Path | None = None) -> None:
    """Forgets all of it, which is what a clean shutdown means."""
    where = directory(home)
    if not where.is_dir():
        return
    for found in where.glob("*.json"):
        found.unlink(missing_ok=True)


def waiting(home: Path | None = None) -> list[Unsaved]:
    """Everything left behind by a session that did not end cleanly.

    Anything unreadable is skipped rather than raised. A launch that fails
    because a recovery file is malformed loses more than the file did.
    """
    where = directory(home)
    if not where.is_dir():
        return []
    found: list[Unsaved] = []
    for entry in sorted(where.glob("*.json")):
        try:
            stored = json.loads(entry.read_text(encoding="utf-8"))
            found.append(
                Unsaved(
                    path=Path(stored["path"]),
                    text=str(stored["text"]),
                    when=datetime.fromisoformat(stored["when"]),
                )
            )
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return found


def is_still_different(found: Unsaved) -> bool:
    """Whether recovering it would actually change anything.

    A buffer whose file already holds the same text is not a recovery, it is a
    prompt about nothing — which is how people learn to dismiss the prompt.
    """
    try:
        return found.path.read_text(encoding="utf-8") != found.text
    except (OSError, UnicodeDecodeError):
        return True


def _name(path: Path) -> str:
    """A flat filename per path. The digest is for uniqueness, not secrecy."""
    digest = hashlib.sha256(str(Path(path).resolve()).encode("utf-8")).hexdigest()[:16]
    return f"{Path(path).name}.{digest}"


def _now() -> datetime:
    return datetime.now(tz=UTC)
