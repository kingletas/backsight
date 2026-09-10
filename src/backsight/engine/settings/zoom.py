"""How large the editor text is, and remembering it.

The most commonly missed shortcut in an editor and the most commonly noticed.
It is the buffer's size only: the chrome around it is a preference somebody
sets once, not something they reach for while reading a file.

Kept as a **step** rather than a size, so the scale in the design tokens stays
the source of truth. Changing `TYPE["code"]` moves every zoom level with it.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

FILE = "zoom.json"

# What one press changes it by. A ratio rather than a number of pixels, so a
# step feels the same at 9px as at 24px.
FACTOR = 1.1

# Small enough to see a whole file, large enough to read across a room. Past
# either end the editor stops being an editor.
SMALLEST = 8.0
LARGEST = 32.0


@dataclass(frozen=True)
class Zoom:
    """One zoom level, as a number of steps away from the design size."""

    base: float
    steps: int = 0

    @property
    def size(self) -> float:
        """The size in pixels, rounded to something GTK renders cleanly."""
        return round(_clamp(self.base * (FACTOR**self.steps)), 1)

    @property
    def is_default(self) -> bool:
        return self.steps == 0

    def bigger(self) -> Zoom:
        return self._moved(1)

    def smaller(self) -> Zoom:
        return self._moved(-1)

    def reset(self) -> Zoom:
        return Zoom(base=self.base, steps=0)

    def _moved(self, by: int) -> Zoom:
        """Refuses to step past the ends rather than pretending it moved."""
        moved = Zoom(base=self.base, steps=self.steps + by)
        if moved.size == self.size and not _within(moved.base * (FACTOR**moved.steps)):
            return self
        return moved


def directory(home: Path | None = None) -> Path:
    if home is not None:
        return Path(home) / ".local" / "state" / "backsight"
    root = os.environ.get("XDG_STATE_HOME")
    base = Path(root) if root else Path.home() / ".local" / "state"
    return base / "backsight"


def read(base: float, home: Path | None = None) -> Zoom:
    """The remembered level, or the design size when there is none."""
    path = directory(home) / FILE
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        steps = int(document["steps"])
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return Zoom(base=base)
    return Zoom(base=base, steps=steps)


def remember(zoom: Zoom, home: Path | None = None) -> Path:
    path = directory(home) / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"steps": zoom.steps}), encoding="utf-8")
    return path


def _clamp(size: float) -> float:
    return max(SMALLEST, min(LARGEST, size))


def _within(size: float) -> bool:
    return SMALLEST <= size <= LARGEST
