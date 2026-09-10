"""Noticing that a file changed underneath you.

A branch switch, a `fmt` in a terminal, a colleague's rebase — all of them
rewrite files the editor is holding in memory. Saving over one of those without
saying so destroys work nobody chose to lose, so the file is stamped when it is
read and the stamp is checked before anything is written.

The stamp is size and modification time rather than a hash. It is cheap enough
to take on every window focus, and the failure it can have is the safe one: two
writes inside the same nanosecond at the same length read as unchanged, which
is a missed prompt rather than a silent overwrite of different content.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Stamp:
    """What a file looked like from the outside when it was read."""

    size: int = -1
    modified: int = -1

    @property
    def exists(self) -> bool:
        return self.size >= 0

    @classmethod
    def of(cls, path: Path) -> Stamp:
        """The current stamp, or an absent one where there is no file."""
        try:
            found = Path(path).stat()
        except OSError:
            return cls()
        return cls(size=found.st_size, modified=found.st_mtime_ns)


class Change:
    """What happened to a file since it was stamped."""

    NOTHING = "nothing"
    EDITED = "edited"
    DELETED = "deleted"


def what_happened(stamp: Stamp, path: Path) -> str:
    """Whether the file changed, went, or is as it was.

    A file that never existed and still does not is `NOTHING`: an unsaved new
    buffer has not been deleted out from under anybody.
    """
    now = Stamp.of(path)
    if now == stamp:
        return Change.NOTHING
    if not now.exists:
        return Change.DELETED if stamp.exists else Change.NOTHING
    return Change.EDITED
