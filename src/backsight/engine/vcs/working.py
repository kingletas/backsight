"""Staging, committing and pushing, without leaving the editor.

FR-APP-03. Everything here is what somebody would otherwise switch to a
terminal for in the middle of a change, and switching is where the plan they
were reading gets lost.

Two things this deliberately does not do. It **never commits what it was not
asked to commit** — staging is explicit, per file, and a commit takes what is
staged rather than everything that happens to have changed. And it **never
pushes on its own**, because a push is outward-facing and irreversible in the
way that matters: somebody else can pull it a second later.

`--porcelain=v2` because its two-character code separates what is staged from
what is not — `1 M.` is staged, `1 .M` is not, and `1 MM` is both. A reader
that treats that as one thing reports a file as staged when half of it is.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from backsight.engine.runner.process import Capture, capture

GIT = "git"
TIMEOUT = 30.0
# A push can take as long as a network takes.
PUSH_TIMEOUT = 300.0


class State(Enum):
    """What has happened to one file, from git's own point of view."""

    STAGED = "staged"
    CHANGED = "changed"
    BOTH = "staged, with more changes since"
    UNTRACKED = "untracked"
    CONFLICTED = "conflicted"


@dataclass(frozen=True)
class Change:
    """One file, and how far along it is."""

    path: str
    state: State

    @property
    def is_staged(self) -> bool:
        return self.state in (State.STAGED, State.BOTH)


@dataclass(frozen=True)
class Working:
    """The working tree, as far as committing is concerned."""

    branch: str = ""
    changes: tuple[Change, ...] = ()
    detached: bool = False
    unreadable: str = ""

    @property
    def staged(self) -> tuple[Change, ...]:
        return tuple(one for one in self.changes if one.is_staged)

    @property
    def unstaged(self) -> tuple[Change, ...]:
        return tuple(one for one in self.changes if not one.is_staged)

    @property
    def is_clean(self) -> bool:
        return not self.changes and not self.unreadable

    @property
    def can_commit(self) -> bool:
        """A commit takes what is staged, so with nothing staged there is none."""
        return bool(self.staged)

    @property
    def can_push(self) -> bool:
        """A push needs a repository with a branch to send.

        An empty `Working` is what a window holds before anything has looked,
        and it has no error in it — so asking whether reading failed said yes,
        push away, in a directory with no repository at all.
        """
        return bool(self.branch) and not self.unreadable and not self.detached

    @property
    def summary(self) -> str:
        if self.unreadable:
            return self.unreadable
        if self.is_clean:
            return f"{self.branch or 'no branch'} — nothing to commit"
        staged = len(self.staged)
        rest = len(self.unstaged)
        said = []
        if staged:
            said.append(f"{staged} staged")
        if rest:
            said.append(f"{rest} not staged")
        return f"{self.branch or 'no branch'} — {', '.join(said)}"


def _state_of(code: str) -> State:
    """The two-character code, read as the two things it is."""
    index, tree = (code + "..")[:2]
    if index == "U" or tree == "U":
        return State.CONFLICTED
    if index != "." and tree != ".":
        return State.BOTH
    if index != ".":
        return State.STAGED
    return State.CHANGED


def read_status(text: str) -> Working:
    """`git status --porcelain=v2 -b`, as the working tree."""
    branch = ""
    detached = False
    changes: list[Change] = []
    for line in text.splitlines():
        if line.startswith("# branch.head "):
            branch = line[len("# branch.head ") :].strip()
            detached = branch == "(detached)"
            continue
        if line.startswith("?"):
            changes.append(Change(path=line[2:].strip(), state=State.UNTRACKED))
            continue
        if line.startswith("u "):
            changes.append(Change(path=line.rsplit(" ", 1)[-1].strip(), state=State.CONFLICTED))
            continue
        if line.startswith(("1 ", "2 ")):
            parts = line.split(" ")
            if len(parts) < 9:
                continue
            # A rename carries `to\tfrom`; what changed is the destination.
            path = " ".join(parts[8:]).split("\t")[0].strip()
            changes.append(Change(path=path, state=_state_of(parts[1])))
    return Working(branch=branch, changes=tuple(changes), detached=detached)


def _git(directory: Path, arguments: list[str], *, timeout: float = TIMEOUT) -> Capture:
    """Runs git, and turns a directory that is not there into an answer.

    Spawning into a missing directory raises rather than failing, so a
    workspace that has been deleted or renamed underneath would take the window
    with it instead of reporting a state.
    """
    try:
        return capture([GIT, *arguments], cwd=Path(directory), timeout=timeout)
    except (OSError, ValueError) as refused:
        return Capture(
            command=tuple([GIT, *arguments]), returncode=1, out="", err=str(refused), seconds=0.0
        )


def status(directory: Path) -> Working:
    """What is here, or why that could not be read."""
    found = _git(directory, ["status", "--porcelain=v2", "-b"])
    if not found.ok:
        return Working(unreadable=_first_line(found) or "This is not a git repository")
    return read_status(found.out)


def stage(directory: Path, paths: list[str]) -> str:
    """Stages exactly what was named. Never everything that changed."""
    if not paths:
        return "Nothing was named, so nothing was staged"
    found = _git(directory, ["add", "--", *paths])
    return "" if found.ok else _first_line(found)


def unstage(directory: Path, paths: list[str]) -> str:
    if not paths:
        return "Nothing was named, so nothing was unstaged"
    found = _git(directory, ["restore", "--staged", "--", *paths])
    return "" if found.ok else _first_line(found)


def commit(directory: Path, message: str) -> str:
    """Commits what is staged. Refuses an empty message rather than opening an
    editor nobody asked for."""
    said = message.strip()
    if not said:
        return "A commit needs a message"
    found = _git(directory, ["commit", "-m", said])
    return "" if found.ok else _first_line(found)


def branches(directory: Path) -> list[str]:
    """Every local branch, current first."""
    found = _git(directory, ["branch", "--format=%(refname:short)"])
    if not found.ok:
        return []
    return [line.strip() for line in found.out.splitlines() if line.strip()]


def switch(directory: Path, branch: str) -> str:
    """Moves to a branch. Git refuses when it would lose work, and so does this."""
    said = branch.strip()
    if not said:
        return "No branch was named"
    found = _git(directory, ["switch", said])
    return "" if found.ok else _first_line(found)


def create_branch(directory: Path, branch: str) -> str:
    said = branch.strip()
    if not said:
        return "No branch was named"
    found = _git(directory, ["switch", "-c", said])
    return "" if found.ok else _first_line(found)


def push(directory: Path, *, remote: str = "", branch: str = "") -> str:
    """Sends it. Never called on its own — always because somebody asked.

    A push is outward-facing and somebody else can pull it a second later,
    which is why nothing here does it as a side effect of anything.
    """
    arguments = ["push"]
    if remote:
        arguments.append(remote)
        if branch:
            arguments.append(branch)
    found = _git(directory, arguments, timeout=PUSH_TIMEOUT)
    return "" if found.ok else _first_line(found)


def clone(url: str, into: Path, *, run=None) -> str:
    """Fetches a repository. The one operation that reaches the network."""
    said = url.strip()
    if not said:
        return "No repository was named"
    runner = run or capture
    found = runner([GIT, "clone", "--", said, str(into)], cwd=Path.cwd(), timeout=PUSH_TIMEOUT)
    return "" if found.ok else _first_line(found)


def _first_line(found: Capture) -> str:
    """What git said, in one line — its first is the one that says why."""
    for stream in (found.err, found.out):
        for line in (stream or "").splitlines():
            if line.strip():
                return line.strip()
    return "git said nothing about what went wrong"
