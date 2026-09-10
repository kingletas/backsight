"""What git can say about one file: its diff, its history, and who wrote it.

**Discarding does not delete.** `git checkout -- file` throws uncommitted work
away with nothing to recover it from, and that is one of the changes people
lose and never get back. This stashes instead, so "discard" is a thing that can
be undone.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backsight.engine.runner.process import Capture, RunTimedOut, capture

SECONDS = 30.0
SEPARATOR = "\x1f"

# One record per commit: hash, author, ISO date, subject.
LOG_FORMAT = f"%H{SEPARATOR}%an{SEPARATOR}%aI{SEPARATOR}%s"


@dataclass(frozen=True)
class Commit:
    """One commit that touched a file."""

    hash: str
    author: str
    when: str
    subject: str

    @property
    def short(self) -> str:
        return self.hash[:8]

    def __str__(self) -> str:
        return f"{self.short}  {self.when[:10]}  {self.author}  {self.subject}"


@dataclass(frozen=True)
class Line:
    """One line of a file, and the commit it last changed in."""

    number: int
    commit: str
    author: str
    when: str

    @property
    def short(self) -> str:
        return self.commit[:8]


@dataclass
class Stashed:
    """A discarded change, and how to get it back."""

    path: Path
    reference: str = ""

    @property
    def recoverable(self) -> bool:
        return bool(self.reference)

    def __str__(self) -> str:
        if not self.recoverable:
            return f"{self.path.name} had nothing to discard"
        return f"Changes to {self.path.name} stashed as {self.reference} — `git stash pop` restores"


def diff(path: Path, *, run=None) -> str:
    """The working change against HEAD, as git renders it."""
    where = Path(path).resolve()
    result = _run(run, ["git", "diff", "--no-color", "--", str(where)], where.parent)
    return result.out if result is not None else ""


def history(path: Path, *, limit: int = 50, run=None) -> list[Commit]:
    """Every commit that touched this file, newest first."""
    result = _run(
        run,
        ["git", "log", f"--format={LOG_FORMAT}", f"-{limit}", "--", str(Path(path).resolve())],
        Path(path).parent,
    )
    if result is None or not result.ok:
        return []
    found: list[Commit] = []
    for line in result.out.splitlines():
        parts = line.split(SEPARATOR)
        if len(parts) != 4:
            # A subject containing the separator would produce more; a broken
            # record is skipped rather than half-read into a wrong commit.
            continue
        found.append(Commit(hash=parts[0], author=parts[1], when=parts[2], subject=parts[3]))
    return found


def blame(path: Path, *, run=None) -> list[Line]:
    """Who last changed each line, in file order."""
    where = Path(path).resolve()
    result = _run(run, ["git", "blame", "--line-porcelain", "--", str(where)], where.parent)
    if result is None or not result.ok:
        return []
    return _read_blame(result.out)


def discard(path: Path, *, run=None) -> Stashed:
    """Puts the working change aside. It is recoverable, not gone.

    A file with nothing to discard is not an error, and says so.
    """
    target = Path(path)
    if not diff(target, run=run).strip():
        return Stashed(path=target)
    result = _run(run, ["git", "stash", "push", "--", str(target.resolve())], target.parent)
    if result is None or not result.ok:
        return Stashed(path=target)
    listed = _run(run, ["git", "stash", "list", "-1"], target.parent)
    reference = ""
    if listed is not None and listed.ok and listed.out.strip():
        reference = listed.out.split(":", 1)[0].strip()
    return Stashed(path=target, reference=reference or "the latest stash")


def _read_blame(out: str) -> list[Line]:
    found: list[Line] = []
    commit = author = when = ""
    number = 0
    for line in out.splitlines():
        if line.startswith("author "):
            author = line[len("author ") :]
        elif line.startswith("author-time "):
            when = line[len("author-time ") :]
        elif line.startswith("\t"):
            found.append(Line(number=number, commit=commit, author=author, when=when))
        elif len(line) >= 40 and " " in line and _looks_like_a_hash(line[:40]):
            parts = line.split()
            commit = parts[0]
            number = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else number + 1
    return found


def _looks_like_a_hash(text: str) -> bool:
    return len(text) == 40 and all(character in "0123456789abcdef" for character in text)


def _run(run, command: list[str], cwd: Path) -> Capture | None:
    """Runs git in the file's own directory, addressing the file absolutely.

    A relative path would be read against `cwd`, which is that same directory —
    so `src/app/main.tf` becomes `src/app/src/app/main.tf` and git reports
    nothing at all, which reads exactly like a file with no history.
    """
    runner = run if run is not None else capture
    try:
        return runner(command, cwd=cwd, timeout=SECONDS)
    except (RunTimedOut, OSError):
        return None
