"""What has been copied lately, so a second copy does not lose the first.

A ring rather than a list: it is bounded, the oldest goes first, and copying the
same thing twice moves it to the front rather than filling the ring with
duplicates.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

DEPTH = 20


@dataclass
class History:
    """The last few things copied, newest first."""

    depth: int = DEPTH
    _items: deque[str] = field(default_factory=deque)

    def remember(self, text: str) -> None:
        """Records a copy. Empty text is not a copy, and a repeat is not a new one."""
        if not text:
            return
        if text in self._items:
            self._items.remove(text)
        self._items.appendleft(text)
        while len(self._items) > self.depth:
            self._items.pop()

    @property
    def items(self) -> list[str]:
        return list(self._items)

    def clear(self) -> None:
        self._items.clear()
