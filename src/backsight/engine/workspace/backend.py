"""Where the state lives, and what it costs when the answer is "here".

`no backend` was a grey subtitle under the workspace name, which is the app's
real first-run problem written as a footnote. State kept on one laptop means
nobody else can plan against it, nothing in CI can, and the record of what
exists in the account is one disk failure from gone.

This reads what is actually there. It does not migrate anything: doing that
means writing a backend block and running an init against a real bucket, and
there is no captured output for that here — so the recovery view says what is
true, offers the part that works, and does not put up a button that cannot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

STATE_FILE = "terraform.tfstate"


@dataclass(frozen=True)
class LocalState:
    """A state file sitting in the working directory."""

    path: Path
    size: int
    written: datetime
    resources: int
    serial: int

    @property
    def is_empty(self) -> bool:
        return self.resources == 0

    def says(self) -> str:
        """One line: how much is in it, and when it last changed."""
        count = f"{self.resources} resource{'' if self.resources == 1 else 's'}"
        return f"{count}, last written {self.written:%-d %B %Y at %H:%M}"


# What having no backend actually takes away. Each of these is a thing somebody
# will try and find they cannot do, so the view names them rather than saying
# "some features are unavailable".
WITHOUT_A_BACKEND = (
    "Nobody else can plan or apply — the record of what exists is on this machine only.",
    "Nothing runs it in CI, for the same reason.",
    "There is no locking, so two applies at once can each overwrite the other.",
    "Losing this disk loses the record of everything that was created.",
)


def local_state(directory: Path) -> LocalState | None:
    """The state file in a module directory, or None where there is not one.

    Unreadable is treated as absent on purpose: the recovery view exists to
    explain a situation, and it cannot explain one it could not read.
    """
    path = Path(directory) / STATE_FILE
    try:
        raw = path.read_text(encoding="utf-8")
        stored = json.loads(raw)
        stat = path.stat()
    except (OSError, ValueError):
        return None
    if not isinstance(stored, dict):
        return None
    resources = stored.get("resources")
    return LocalState(
        path=path,
        size=stat.st_size,
        written=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        resources=len(resources) if isinstance(resources, list) else 0,
        serial=int(stored.get("serial", 0) or 0),
    )
