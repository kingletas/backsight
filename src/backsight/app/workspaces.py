"""Which workspaces are known, and which one is open.

The header used to carry an accent-filled "Open workspace" button pinned to the
top-left. That is the primary action for the few seconds before a workspace is
open and never again, and it sat in the position GNOME readers use for
back-navigation or a sidebar toggle. It is one row in a switcher now.

Recent workspaces are **state, not configuration**: the person did not write
them, and nothing is lost by deleting the file. They live beside the remembered
layouts for that reason.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

FILE = "workspaces.json"

# Eight. A list long enough to scroll is a list nobody reads to the end of.
LIMIT = 8


@dataclass(frozen=True)
class Known:
    """One workspace somebody has opened."""

    path: Path
    backend: str = ""
    state: str = ""
    environment: str = ""

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def exists(self) -> bool:
        return self.path.is_dir()

    def summary(self) -> str:
        """The second line: where it is, and what is true of it.

        A workspace whose directory has gone says so instead of its backend.
        The absence is the useful information, and it is shown once — the next
        launch drops it.
        """
        if not self.exists:
            return f"{_short(self.path)} · missing"
        return " · ".join(part for part in (_short(self.path), self.backend, self.state) if part)

    @property
    def state_class(self) -> str:
        """The consequence vocabulary, not a colour picked here."""
        if not self.exists:
            return "tf-nostate"
        if "local" in self.state:
            return "tf-nostate"
        if "drift" in self.state:
            return "tf-drift"
        return "tf-faint"


def directory(home: Path | None = None) -> Path:
    if home is not None:
        return Path(home) / ".local" / "state" / "backsight"
    root = os.environ.get("XDG_STATE_HOME")
    base = Path(root) if root else Path.home() / ".local" / "state"
    return base / "backsight"


def read(home: Path | None = None) -> list[Known]:
    """Everything known, newest first, with anything gone already dropped."""
    path = directory(home) / FILE
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    found = []
    for entry in document if isinstance(document, list) else []:
        if not isinstance(entry, dict) or not entry.get("path"):
            continue
        found.append(
            Known(
                path=Path(entry["path"]),
                backend=str(entry.get("backend", "")),
                state=str(entry.get("state", "")),
                environment=str(entry.get("environment", "")),
            )
        )
    return found[:LIMIT]


def remember(workspace: Known, home: Path | None = None) -> list[Known]:
    """Puts one at the front, and drops anything that is no longer there.

    A missing workspace is shown once and removed on the next launch, so this
    prunes on write rather than on read: the row somebody saw is the last time
    they will see it.
    """
    kept = [known for known in read(home) if known.path != workspace.path and known.exists]
    found = [workspace, *kept][:LIMIT]
    path = directory(home) / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [
                {
                    "path": str(known.path),
                    "backend": known.backend,
                    "state": known.state,
                    "environment": known.environment,
                }
                for known in found
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    return found


def _short(path: Path) -> str:
    """A path as somebody would say it, with home as a tilde."""
    try:
        return f"~/{path.relative_to(Path.home()).as_posix()}"
    except ValueError:
        return str(path)
