"""Finding text and files across a workspace.

Both work on what is on disk rather than on what is open, because the answer to
"where is this used" is usually in a file nobody has opened.

Neither shells out. `grep` would be faster on a very large tree and would bring
its own quoting, its own exit codes and its own absence on some machines, for a
workspace that is measured in hundreds of files.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# Never walked into. These hold provider binaries and cached modules — hundreds
# of megabytes that no search of somebody's own code should read.
SKIP = {".terraform", ".git", ".backsight", "node_modules", "__pycache__"}

# What a text search reads. A search that opened every file would read provider
# binaries and lock files nobody wrote.
TEXT = {".tf", ".tfvars", ".hcl", ".json", ".yaml", ".yml", ".md", ".toml", ".txt"}

LIMIT = 500


@dataclass(frozen=True)
class Hit:
    """One match: where it is, and the line it is on."""

    path: Path
    line: int
    text: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}  {self.text.strip()}"


def files_named(root: Path, term: str, *, limit: int = LIMIT) -> list[Path]:
    """Every file whose name contains the term, case-insensitively."""
    wanted = term.strip().lower()
    if not wanted:
        return []
    found = [path for path in _walk(root) if wanted in path.name.lower()]
    return sorted(found)[:limit]


def text_in(
    root: Path,
    term: str,
    *,
    regex: bool = False,
    case_sensitive: bool = False,
    limit: int = LIMIT,
    suffixes: Iterable[str] | None = None,
) -> list[Hit]:
    """Every line containing the term, in file order.

    A bad regular expression is reported as no matches rather than raised: it
    is something the person is still typing, not a fault.
    """
    if not term:
        return []
    try:
        pattern = re.compile(term if regex else re.escape(term), 0 if case_sensitive else re.I)
    except re.error:
        return []

    allowed = set(suffixes) if suffixes is not None else TEXT
    found: list[Hit] = []
    for path in sorted(_walk(root)):
        if path.suffix.lower() not in allowed:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            # A file that is not text, or vanished, is not a reason to stop.
            continue
        for number, line in enumerate(content.splitlines(), start=1):
            if pattern.search(line):
                found.append(Hit(path=path, line=number, text=line))
                if len(found) >= limit:
                    return found
    return found


def _walk(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in Path(root).rglob("*"):
        if not path.is_file():
            continue
        if SKIP & set(path.relative_to(root).parts):
            continue
        found.append(path)
    return found
