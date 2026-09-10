"""One thing in the library, and the file it is written in.

An entry is **a Terraform file with a comment header**. Not TOML, not JSON, not
a database: somebody writing one is writing HCL, and this way they write it in
this editor with highlighting and `tofu fmt` working on it, review it in a diff
that reads like code, and share it by committing it.

    # name: Private bucket with access logs
    # kind: recipe
    # tags: s3, storage, encryption
    # about: A bucket nothing outside the account can reach, with encryption
    #        and a log target. The pair is the point — a bucket with logging
    #        and no encryption passes review and fails an audit.

    resource "aws_s3_bucket" "${1:name}" { ... }

A runbook is the same file with `# step:` lines dividing it, because a
procedure is an ordered set of things to do and each of them is usually a block
to insert or a command to run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

SUFFIX = ".tf"

# A header line is a comment, a key, a colon, and the value. A continuation is
# a comment line that begins with whitespace, so prose can wrap.
HEADER = re.compile(r"^#\s*([a-z][a-z_]*)\s*:\s*(.*)$")
CONTINUATION = re.compile(r"^#\s{2,}(\S.*)$")
STEP = re.compile(r"^#\s*step\s*:\s*(.*)$", re.IGNORECASE)
RUNS = re.compile(r"^#\s*run\s*:\s*(.*)$", re.IGNORECASE)


class Kind(Enum):
    """What you do with it, which is the only way these differ."""

    SNIPPET = "snippet"
    EXAMPLE = "example"
    RECIPE = "recipe"
    RUNBOOK = "runbook"

    @property
    def label(self) -> str:
        return {
            Kind.SNIPPET: "Snippet",
            Kind.EXAMPLE: "Example",
            Kind.RECIPE: "Recipe",
            Kind.RUNBOOK: "Runbook",
        }[self]

    @property
    def what_it_does(self) -> str:
        """The verb on the button, because they are not all "insert"."""
        return {
            Kind.SNIPPET: "Insert",
            Kind.EXAMPLE: "Open as a new file",
            Kind.RECIPE: "Insert",
            Kind.RUNBOOK: "Open",
        }[self]


class Source(Enum):
    """Where an entry came from, which decides what may be done to it."""

    BUILT_IN = "built in"
    YOURS = "yours"
    WORKSPACE = "this workspace"
    SHARED = "shared"

    @property
    def is_editable(self) -> bool:
        """A generated entry has no file, and a shared one is not ours."""
        return self in (Source.YOURS, Source.WORKSPACE)


@dataclass(frozen=True)
class Step:
    """One thing to do in a runbook, and how to do it."""

    title: str
    body: str = ""
    command: str = ""

    @property
    def is_a_command(self) -> bool:
        return bool(self.command)


@dataclass(frozen=True)
class Entry:
    """One snippet, example, recipe or runbook."""

    name: str
    kind: Kind = Kind.SNIPPET
    body: str = ""
    about: str = ""
    tags: tuple[str, ...] = ()
    source: Source = Source.YOURS
    path: Path | None = None
    steps: tuple[Step, ...] = ()
    # A resource type, where the entry is about one. Lets the library answer
    # "what have I got for an aws_s3_bucket" from the cursor.
    resource: str = ""

    @property
    def is_a_runbook(self) -> bool:
        return self.kind is Kind.RUNBOOK

    def matches(self, term: str) -> bool:
        """Whether a search term reaches this entry.

        Everything a person might remember about it: the name, what it is for,
        its tags, the resource type it is about, and the text itself — somebody
        looking for the bucket snippet may only remember `force_destroy`.
        """
        wanted = term.strip().lower()
        if not wanted:
            return True
        haystack = " ".join(
            (self.name, self.about, self.resource, " ".join(self.tags), self.body)
        ).lower()
        return all(word in haystack for word in wanted.split())


@dataclass
class Broken:
    """A file in a library directory that will not read as an entry.

    Reported rather than skipped. A snippet somebody wrote that silently never
    appears is worse than one that appears with a complaint attached.
    """

    path: Path
    why: str
    entries: list = field(default_factory=list)


def parse(text: str, *, path: Path | None = None, source: Source = Source.YOURS) -> Entry | Broken:
    """Reads one file. A file with no `# name:` is not an entry."""
    header, body = _split(text)
    name = header.get("name", "").strip()
    if not name:
        return Broken(path=path or Path("<text>"), why="it has no `# name:` line")

    try:
        kind = Kind(header.get("kind", "snippet").strip().lower())
    except ValueError:
        return Broken(
            path=path or Path("<text>"),
            why=f"`{header.get('kind')}` is not one of " + ", ".join(one.value for one in Kind),
        )

    tags = tuple(
        part.strip() for part in header.get("tags", "").replace(",", " ").split() if part.strip()
    )
    steps = _steps(body) if kind is Kind.RUNBOOK else ()
    return Entry(
        name=name,
        kind=kind,
        body=body.strip("\n") + "\n" if body.strip() else "",
        about=header.get("about", "").strip(),
        tags=tags,
        source=source,
        path=path,
        steps=steps,
        resource=header.get("resource", "").strip(),
    )


def _split(text: str) -> tuple[dict[str, str], str]:
    """The header comment block, and everything after it.

    The header ends at the first line that is not a comment. A comment further
    down is a comment about the code, which is the ordinary case and not
    metadata that happened to be late.
    """
    header: dict[str, str] = {}
    lines = text.splitlines()
    at = 0
    last = ""
    for line in lines:
        if not line.strip():
            if not header:
                at += 1
                continue
            at += 1
            break
        if not line.lstrip().startswith("#"):
            break
        found = HEADER.match(line.strip())
        carried = CONTINUATION.match(line.rstrip())
        if found and not STEP.match(line.strip()):
            last = found.group(1)
            header[last] = found.group(2).strip()
        elif carried and last:
            header[last] = f"{header[last]} {carried.group(1).strip()}".strip()
        elif not header:
            # A comment before any header line is just a comment.
            break
        at += 1
    return header, "\n".join(lines[at:])


def _steps(body: str) -> tuple[Step, ...]:
    """A runbook's steps, in the order they are written."""
    found: list[Step] = []
    title = ""
    command = ""
    collected: list[str] = []

    def keep() -> None:
        if title:
            found.append(Step(title=title, body="\n".join(collected).strip("\n"), command=command))

    for line in body.splitlines():
        heading = STEP.match(line.strip())
        if heading:
            keep()
            title, command, collected = heading.group(1).strip(), "", []
            continue
        runs = RUNS.match(line.strip())
        if runs and title:
            command = runs.group(1).strip()
            continue
        if title:
            collected.append(line)
    keep()
    return tuple(found)


def write(entry: Entry) -> str:
    """The file this entry would be saved as, header and all."""
    lines = [f"# name: {entry.name}", f"# kind: {entry.kind.value}"]
    if entry.resource:
        lines.append(f"# resource: {entry.resource}")
    if entry.tags:
        lines.append(f"# tags: {', '.join(entry.tags)}")
    if entry.about:
        lines.append(f"# about: {entry.about}")
    return "\n".join(lines) + "\n\n" + entry.body.strip("\n") + "\n"


def file_name(name: str) -> str:
    """A file name somebody can find in a directory listing."""
    said = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return f"{said or 'entry'}{SUFFIX}"
