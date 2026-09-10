"""What was open last time, so opening the app returns you to your work.

Two separate things, kept apart on purpose. **Geometry** is about the window and
belongs to the machine — a size that suits a laptop is wrong on the monitor at
the desk. **The session** is about the files and belongs to the workspace, so
two workspaces do not fight over one list of open tabs.

Neither is ever allowed to stop the application starting. Everything here reads
defensively and returns nothing rather than raising: a corrupt state file is a
lost layout, never a launch failure.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

GEOMETRY = "geometry.json"
SESSION = "session.json"

# Smaller than this and the window cannot show a sidebar and a file at once, so
# a stored size below it came from something going wrong rather than a choice.
LEAST_WIDE = 640
LEAST_TALL = 480


@dataclass(frozen=True)
class Geometry:
    """How large the window was, and whether it was maximised."""

    width: int = 1280
    height: int = 820
    maximised: bool = False
    sidebar: int = 240

    @property
    def is_sane(self) -> bool:
        return self.width >= LEAST_WIDE and self.height >= LEAST_TALL


@dataclass(frozen=True)
class OpenFile:
    """One tab, and where the caret and the view were in it."""

    path: str
    line: int = 1
    column: int = 0
    scroll: float = 0.0


@dataclass(frozen=True)
class Session:
    """Everything that was open in one workspace."""

    files: list[OpenFile] = field(default_factory=list)
    active: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.files


def directory(home: Path | None = None) -> Path:
    if home is not None:
        return Path(home) / ".local" / "state" / "backsight"
    root = os.environ.get("XDG_STATE_HOME")
    base = Path(root) if root else Path.home() / ".local" / "state"
    return base / "backsight"


def read_geometry(home: Path | None = None) -> Geometry:
    stored = _load(directory(home) / GEOMETRY)
    if not isinstance(stored, dict):
        return Geometry()
    try:
        found = Geometry(
            width=int(stored.get("width", 1280)),
            height=int(stored.get("height", 820)),
            maximised=bool(stored.get("maximised", False)),
            sidebar=int(stored.get("sidebar", 240)),
        )
    except (TypeError, ValueError):
        return Geometry()
    # A window restored to 40x12 cannot be used and cannot be resized back by
    # somebody who cannot see its edges.
    return found if found.is_sane else Geometry()


def remember_geometry(geometry: Geometry, home: Path | None = None) -> None:
    _save(directory(home) / GEOMETRY, asdict(geometry))


def read_session(workspace: Path | str, home: Path | None = None) -> Session:
    stored = _load(directory(home) / SESSION)
    found = (stored or {}).get(str(workspace)) if isinstance(stored, dict) else None
    if not isinstance(found, dict):
        return Session()
    files = []
    for entry in found.get("files") or []:
        if not isinstance(entry, dict) or not entry.get("path"):
            continue
        try:
            files.append(
                OpenFile(
                    path=str(entry["path"]),
                    line=max(1, int(entry.get("line", 1))),
                    column=max(0, int(entry.get("column", 0))),
                    scroll=float(entry.get("scroll", 0.0)),
                )
            )
        except (TypeError, ValueError):
            continue
    return Session(files=files, active=str(found.get("active", "")))


def remember_session(workspace: Path | str, session: Session, home: Path | None = None) -> None:
    """Records one workspace's session, leaving every other workspace's alone."""
    path = directory(home) / SESSION
    stored = _load(path)
    if not isinstance(stored, dict):
        stored = {}
    stored[str(workspace)] = {
        "files": [asdict(found) for found in session.files],
        "active": session.active,
    }
    _save(path, stored)


def _load(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(path: Path, document: object) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        beside = path.with_suffix(".json.writing")
        beside.write_text(json.dumps(document, indent=2), encoding="utf-8")
        os.replace(beside, path)
    except OSError:
        # Losing a layout is not worth failing a shutdown over.
        return
