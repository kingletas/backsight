"""Creating, renaming, copying and removing files in a workspace.

**Nothing here deletes.** Removing goes to the trash, because two of the real
data losses behind this rule were one-click removals with no way back, and a
file somebody spent an afternoon on is not worth the saved millisecond.

Every operation refuses rather than overwriting. Silently replacing a file
because a name collided is the failure that produces "where did my module go".
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


class Refused(Exception):
    """An operation that would have destroyed something, and did not."""


@dataclass(frozen=True)
class Removed:
    """What was removed, and where it went."""

    path: Path
    trashed: bool

    def __str__(self) -> str:
        where = "the trash" if self.trashed else "nowhere — it is gone"
        return f"{self.path.name} moved to {where}"


def create(path: Path, *, content: str = "") -> Path:
    """Makes a new file. Refuses if anything is already there."""
    target = Path(path)
    if target.exists():
        raise Refused(f"{target.name} already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def create_folder(path: Path) -> Path:
    target = Path(path)
    if target.exists():
        raise Refused(f"{target.name} already exists")
    target.mkdir(parents=True)
    return target


def rename(path: Path, name: str) -> Path:
    """Renames within the same directory. The name is a name, not a path."""
    source = Path(path)
    if "/" in name or name in ("", ".", ".."):
        raise Refused(f"{name!r} is not a file name")
    target = source.parent / name
    if target == source:
        return source
    if target.exists():
        raise Refused(f"{name} already exists")
    source.rename(target)
    return target


def duplicate(path: Path) -> Path:
    """Copies a file beside itself, finding a name nothing else has."""
    source = Path(path)
    if not source.is_file():
        raise Refused(f"{source.name} is not a file")
    for attempt in range(1, 1000):
        suffix = " copy" if attempt == 1 else f" copy {attempt}"
        target = source.with_name(f"{source.stem}{suffix}{source.suffix}")
        if not target.exists():
            shutil.copy2(source, target)
            return target
    raise Refused("a thousand copies is enough")


def move(path: Path, directory: Path) -> Path:
    """Moves a file into a directory, refusing to overwrite what is there."""
    source = Path(path)
    target = Path(directory) / source.name
    if target == source:
        return source
    if target.exists():
        raise Refused(f"{source.name} already exists in {Path(directory).name}")
    Path(directory).mkdir(parents=True, exist_ok=True)
    source.rename(target)
    return target


def remove(path: Path, *, to_trash: Callable[[Path], None]) -> Removed:
    """Moves a file to the trash. **Never deletes.**

    The trash itself belongs to the desktop, so it arrives as a callable — the
    engine states the policy and the interface performs it. There is no
    fallback: where trashing fails, this refuses and leaves the file where it
    is. A fallback that quietly turns "move to trash" into "delete" is worse
    than the operation not existing.
    """
    source = Path(path)
    if not source.exists():
        raise Refused(f"{source.name} is not there")
    try:
        to_trash(source)
    except Exception as refused:  # noqa: BLE001 — the desktop decides how it fails
        raise Refused(
            f"{source.name} could not be moved to the trash: {refused}. "
            "It has been left where it is."
        ) from refused
    return Removed(path=source, trashed=True)
