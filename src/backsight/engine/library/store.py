"""Where entries come from, and which one wins when two share a name.

Four places, in the same order settings use, and for the same reason: a person
overriding something they were given must not have to argue with it.

1. **Built in** — generated from the provider schema, so the library is never
   empty for a resource somebody is about to write.
2. **Shared** — a directory a platform team distributes, usually a cloned git
   repository named in settings.
3. **This workspace** — `.backsight/library/`, committed with the code, so an
   entry travels with the repository that needs it.
4. **Yours** — your own, in your config directory, and last because your own
   copy of an entry is the one you meant.

A file that will not read is reported rather than skipped. An entry somebody
wrote that silently never appears is worse than one that appears with a
complaint attached.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from backsight.engine.library.entry import SUFFIX, Broken, Entry, Kind, Source, file_name, parse

DIRECTORY = "library"
IN_A_WORKSPACE = Path(".backsight") / DIRECTORY

# What ships with the application. The Terraform language constructs people get
# wrong — `moved`, `import`, `for_each`, `dynamic`, `lifecycle` — plus two
# examples and two runbooks. A library with nothing in it is a mechanism rather
# than a feature, and the first thing anybody does is look.
SHIPPED = Path(__file__).parent / "shipped"

# Last wins. Built-in first because everything else is somebody's decision.
ORDER = (Source.BUILT_IN, Source.SHARED, Source.WORKSPACE, Source.YOURS)


def yours(home: Path | None = None) -> Path:
    """Your own entries, beside your settings."""
    if home is not None:
        return Path(home) / ".config" / "backsight" / DIRECTORY
    root = os.environ.get("XDG_CONFIG_HOME")
    base = Path(root) if root else Path.home() / ".config"
    return base / "backsight" / DIRECTORY


def in_workspace(workspace: Path) -> Path:
    return Path(workspace) / IN_A_WORKSPACE


@dataclass
class Library:
    """Everything reusable, from wherever it came from."""

    entries: list[Entry] = field(default_factory=list)
    broken: list[Broken] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.entries)

    def search(self, term: str = "", *, kind: Kind | None = None) -> list[Entry]:
        """What matches, best first.

        Ordered by how well the term fits rather than alphabetically: a name
        that starts with what you typed is what you meant, and an entry that
        only matches somewhere in its body is a fallback.
        """
        wanted = term.strip().lower()
        found = [
            entry
            for entry in self.entries
            if entry.matches(term) and (kind is None or entry.kind is kind)
        ]
        return sorted(found, key=lambda entry: (_closeness(entry, wanted), entry.name.lower()))

    def for_resource(self, type_: str) -> list[Entry]:
        """Everything about one resource type, for answering from the cursor."""
        return [entry for entry in self.entries if entry.resource == type_]

    def named(self, name: str) -> Entry | None:
        return next((entry for entry in self.entries if entry.name == name), None)

    @property
    def kinds(self) -> dict[Kind, int]:
        found: dict[Kind, int] = {}
        for entry in self.entries:
            found[entry.kind] = found.get(entry.kind, 0) + 1
        return found


def _closeness(entry: Entry, wanted: str) -> int:
    if not wanted:
        return 0
    name = entry.name.lower()
    if name.startswith(wanted):
        return 0
    if wanted in name:
        return 1
    if wanted in entry.resource.lower() or wanted in " ".join(entry.tags).lower():
        return 2
    return 3


def read_directory(where: Path, source: Source) -> tuple[list[Entry], list[Broken]]:
    """Every entry in one directory, and every file that would not read."""
    found: list[Entry] = []
    broken: list[Broken] = []
    directory = Path(where)
    if not directory.is_dir():
        return found, broken
    for path in sorted(directory.rglob(f"*{SUFFIX}")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as refused:
            broken.append(Broken(path=path, why=str(refused)))
            continue
        read = parse(text, path=path, source=source)
        broken.append(read) if isinstance(read, Broken) else found.append(read)
    return found, broken


def load(
    *,
    workspace: Path | None = None,
    shared: Path | None = None,
    home: Path | None = None,
    generated: list[Entry] | None = None,
) -> Library:
    """Every source, in order, with a later name replacing an earlier one."""
    by_name: dict[str, Entry] = {}
    broken: list[Broken] = []

    shipped, broken_here = read_directory(SHIPPED, Source.BUILT_IN)
    broken.extend(broken_here)
    for entry in shipped:
        by_name[entry.name] = entry

    for entry in generated or []:
        by_name[entry.name] = entry

    places = [
        (shared, Source.SHARED),
        (in_workspace(workspace) if workspace else None, Source.WORKSPACE),
        (yours(home), Source.YOURS),
    ]
    for where, source in places:
        if where is None:
            continue
        entries, unreadable = read_directory(where, source)
        broken.extend(unreadable)
        for entry in entries:
            by_name[entry.name] = entry

    return Library(entries=list(by_name.values()), broken=broken)


def save(entry: Entry, *, home: Path | None = None, workspace: Path | None = None) -> Path:
    """Writes an entry where its source says it belongs, and says where.

    A workspace entry is committed with the code; yours is not. Which one
    somebody wanted is a decision they made when they saved it, so it is
    carried on the entry rather than asked again here.
    """
    from backsight.engine.library.entry import write

    where = (
        in_workspace(workspace)
        if entry.source is Source.WORKSPACE and workspace is not None
        else yours(home)
    )
    where.mkdir(parents=True, exist_ok=True)
    path = where / file_name(entry.name)
    beside = path.with_suffix(".tf.writing")
    beside.write_text(write(entry), encoding="utf-8")
    os.replace(beside, path)
    return path
