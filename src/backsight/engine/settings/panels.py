"""How tall the bottom panel is, per workspace.

The default is what the content asks for, capped — one diagnostic taking 40%
of the window is the panel deciding the failure is more important than the file
it happened in.

A dragged height is remembered, but **only once it has been dragged**. Storing
the computed default would freeze whatever the first plan happened to need, and
the next workspace would open at a height nobody chose.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

FILE = "panels.json"

# **Two ceilings, because a height is chosen in two ways.**
#
# Growing itself: one diagnostic filling nearly half the window is the panel
# deciding the failure matters more than the file it happened in, so content
# stops here and scrolls instead.
GROWS_TO = 0.45

# Dragged: you asked for it. A drawer that fills the window is a screen, and a
# screen needs a way back that a drawer does not have — so it stops short of
# one.
DRAGS_TO = 0.70

# What it opens at before anybody has an opinion, so first open is the same
# fraction every time rather than a function of what happens to be in it.
OPENS_AT = 0.38

# Under this there is not enough room for a heading and a sentence, so it would
# be a scrollbar pretending to be a panel.
LEAST = 140


def directory(home: Path | None = None) -> Path:
    if home is not None:
        return Path(home) / ".local" / "state" / "backsight"
    root = os.environ.get("XDG_STATE_HOME")
    base = Path(root) if root else Path.home() / ".local" / "state"
    return base / "backsight"


def height_for(wanted: int, window: int, *, dragged: bool = False) -> int:
    """What the panel actually gets: what it asked for, within the bounds.

    `dragged` says which ceiling applies. A height somebody chose is allowed
    further than a height the content asked for.
    """
    if window <= 0:
        return LEAST
    cap = int(window * (DRAGS_TO if dragged else GROWS_TO))
    return max(min(LEAST, cap), min(wanted, cap))


def first_height(window: int) -> int:
    """What a drawer nobody has dragged in this workspace opens at."""
    if window <= 0:
        return LEAST
    return max(LEAST, int(window * OPENS_AT))


def read(workspace: str, home: Path | None = None) -> int | None:
    """The height this workspace was left at, or None if never dragged."""
    try:
        stored = json.loads((directory(home) / FILE).read_text(encoding="utf-8"))
        found = stored["drawer"][workspace]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return found if isinstance(found, int) and found > 0 else None


def remember(workspace: str, height: int, home: Path | None = None) -> None:
    """Records a height somebody chose by dragging it."""
    where = directory(home)
    where.mkdir(parents=True, exist_ok=True)
    path = where / FILE
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stored = {}
    if not isinstance(stored, dict):
        stored = {}
    stored.setdefault("drawer", {})[workspace] = int(height)
    path.write_text(json.dumps(stored, indent=2), encoding="utf-8")
