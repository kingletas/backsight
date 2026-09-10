"""What was reached for last, so the palette opens on it.

FR-APP-11. An occasional user cannot search for a command they do not know
exists, and the palette's suggestions are the only affordance between them and
a blank prompt. A fixed list of suggestions answers that once; what somebody
actually reaches for answers it every time after.

Newest first, and short. A list of thirty recents is a second wall.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

FILE = "recents.json"

# Enough to cover what somebody is doing today. More is a list to read rather
# than a row to glance at.
MOST = 6


def directory(home: Path | None = None) -> Path:
    if home is not None:
        return Path(home) / ".local" / "state" / "backsight"
    root = os.environ.get("XDG_STATE_HOME")
    base = Path(root) if root else Path.home() / ".local" / "state"
    return base / "backsight"


def read(home: Path | None = None) -> list[str]:
    """The actions last chosen, newest first."""
    try:
        stored = json.loads((directory(home) / FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(stored, list):
        return []
    return [str(one) for one in stored if isinstance(one, str)][:MOST]


def remember(action: str, *, home: Path | None = None) -> list[str]:
    """Puts one at the front, and never twice.

    A command chosen again moves rather than repeating: two rows for one
    command is the list being wrong about what it holds.
    """
    said = action.strip()
    if not said:
        return read(home)
    found = [one for one in read(home) if one != said]
    found.insert(0, said)
    found = found[:MOST]

    where = directory(home)
    try:
        where.mkdir(parents=True, exist_ok=True)
        path = where / FILE
        beside = path.with_suffix(".json.writing")
        beside.write_text(json.dumps(found), encoding="utf-8")
        os.replace(beside, path)
    except OSError:
        # Losing the list must never lose the command somebody just ran.
        return found
    return found
