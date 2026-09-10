"""The file tree, one level at a time.

**The rail is a filesystem explorer, not a search result.** It shows the
repository's immediate children and nothing below them until somebody asks —
which is the difference between navigating a repository and having one dumped
on you.

The version this replaces listed every *module* it could find, with its path
flattened into the row: `examples/account-baseline/`, `examples/data-pipeline/`,
`modules/cognito-user-pool/`, as peers, with their files under them. On a real
repository that is 63 rows of flattened path and 273 files, the hierarchy is
gone, and the top of the tree is below the fold before it has been read.

Four rules, and every one of them is about what is **not** drawn:

1. **One level.** Reading a directory yields its own children and stops.
2. **Collapsed until asked.** Expanding a directory reveals its children and
   leaves *those* collapsed.
3. **Files only under an open directory.** A file is never in the tree because
   its directory exists somewhere in the repository.
4. **Revealing a file opens its ancestors and nothing else.**

Nothing here reads more of the disk than one directory at a time, which is what
keeps a repository of any size affordable.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Machinery rather than content. **Every other dotfile stays**: `.tflint.hcl`,
# `.checkov.yml` and `.pre-commit-config.yaml` are as much a part of an
# infrastructure repository as its `.tf` files, and hiding them because a file
# manager would is a convention borrowed from the wrong application.
HIDDEN = frozenset({".git", ".terraform", "__pycache__", ".pytest_cache", ".ruff_cache"})

# How far a search will walk before it stops and says so. A filter that reads a
# hundred thousand files to answer a three-letter question is one people learn
# not to type in.
MOST = 5_000


@dataclass(frozen=True)
class Entry:
    """One row: a directory or a file, and where it is."""

    path: Path
    is_dir: bool

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def shown(self) -> str:
        """A folder says it is one, on the side a reader looks for it.

        `network` and `network.tf` were one glyph apart, and the glyph was on
        the wrong side of the word.
        """
        return f"{self.name}/" if self.is_dir else self.name

    @property
    def described(self) -> str:
        """What a screen reader is told, which has to say which kind it is."""
        return f"{self.name}, folder" if self.is_dir else f"{self.name}, file"


def children(directory: Path) -> list[Entry]:
    """The immediate children of one directory. **Directories first, then files.**

    Alphabetical within each, case-insensitively, so `README.md` and `main.tf`
    sort the way a reader expects rather than the way bytes do. A directory
    that cannot be read is empty rather than an exception: a permission denied
    halfway down a tree is not a reason for the rail to stop.
    """
    try:
        found = list(directory.iterdir())
    except OSError:
        return []
    kept = [one for one in found if one.name not in HIDDEN]
    entries = [Entry(path=one, is_dir=one.is_dir()) for one in kept]
    return sorted(entries, key=lambda entry: (not entry.is_dir, entry.name.casefold()))


def has_children(directory: Path) -> bool:
    """Whether a directory would draw anything if it were opened.

    Asked so an empty folder does not offer a chevron that reveals nothing.
    """
    try:
        return any(one.name not in HIDDEN for one in directory.iterdir())
    except OSError:
        return False


def ancestors(path: Path, root: Path) -> list[Path]:
    """The directories to open to reveal a path, outermost first.

    **Only these.** Revealing `modules/cognito-user-pool/main.tf` opens
    `modules` and `cognito-user-pool`, and leaves every other module alone —
    which is the whole difference between revealing a file and re-expanding the
    repository.
    """
    try:
        inside = path.resolve().relative_to(root.resolve())
    except ValueError:
        return []
    found: list[Path] = []
    where = root.resolve()
    for part in inside.parts[:-1]:
        where = where / part
        found.append(where)
    return found


def matching(root: Path, term: str, *, limit: int = MOST) -> list[Path]:
    """Every file whose name contains the term, walking one directory at a time.

    Directories are walked but not returned: a filter is for finding a file,
    and the folders on the way are what `ancestors` puts back.
    """
    wanted = term.strip().casefold()
    if not wanted:
        return []
    found: list[Path] = []
    seen = 0
    queue = [root]
    while queue and seen < limit:
        for entry in children(queue.pop(0)):
            seen += 1
            if entry.is_dir:
                queue.append(entry.path)
                continue
            if wanted in entry.name.casefold():
                found.append(entry.path)
    return found
