"""Stack definitions, read from a file that lives in version control.

BRD §6.11. A workspace is a directory; a **stack** is a deployable unit with an
identity. The distinction matters because dependencies exist between deployable
units, not between folders.

Three decisions from the BRD shape everything here:

- **DD-13: the graph lives in version control**, not in application state. It is
  shared by committing a file, so nothing here writes to a database or a cache.
- **DD-14: dependencies are declared, never inferred.** Inferring them from
  remote state data sources looks clever and is wrong often enough to be
  dangerous — a wrong graph produces a confident, incorrect blast radius.
- **DD-15: v1 computes apply order and a person executes it**, one stack at a
  time. Nothing here applies anything.

Everything in this module works offline — FR-STK-09.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

FILE = "stacks.toml"
DIRECTORY = ".backsight"


@dataclass(frozen=True)
class Binding:
    """Where a stack deploys to. Absent is honest; guessed is not."""

    account: str = ""
    role: str = ""
    region: str = ""

    @property
    def is_stated(self) -> bool:
        return bool(self.account or self.role)

    def __str__(self) -> str:
        return " · ".join(part for part in (self.account, self.region, self.role) if part)


@dataclass(frozen=True)
class Stack:
    """One deployable unit."""

    name: str
    path: str
    engine: str = "tofu"
    version: str = ""
    backend: str = ""
    environment: str = ""
    variables: dict[str, str] = field(default_factory=dict)
    binding: Binding = field(default_factory=Binding)
    # What this stack publishes for others to consume.
    outputs: tuple[str, ...] = ()
    # Declared edges: which stack this one needs, and which of its outputs.
    needs: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def upstream(self) -> tuple[str, ...]:
        return tuple(sorted(self.needs))


@dataclass(frozen=True)
class Problem:
    """Something wrong with the definitions, said plainly."""

    stack: str
    detail: str

    def __str__(self) -> str:
        return f"{self.stack}: {self.detail}" if self.stack else self.detail


@dataclass
class Definitions:
    """Every stack in a workspace, and everything wrong with them.

    Problems are carried rather than raised: a file with one bad edge should
    still show the other nine stacks, or a typo hides the whole graph.
    """

    stacks: dict[str, Stack] = field(default_factory=dict)
    problems: list[Problem] = field(default_factory=list)
    path: Path | None = None

    @property
    def is_declared(self) -> bool:
        """Whether this workspace has a stack file at all."""
        return self.path is not None

    @property
    def ok(self) -> bool:
        return not self.problems

    def get(self, name: str) -> Stack | None:
        return self.stacks.get(name)

    def containing(self, path: Path) -> Stack | None:
        """Which stack a file belongs to, by the deepest path that contains it.

        Deepest wins: a stack at `infra` and one at `infra/network` both contain
        `infra/network/main.tf`, and the answer is the more specific one.
        """
        if self.path is None:
            return None
        root = self.path.parent.parent
        try:
            relative = Path(path).resolve().relative_to(root.resolve())
        except ValueError:
            return None
        found: Stack | None = None
        for stack in self.stacks.values():
            where = Path(stack.path)
            if where in relative.parents or where == relative.parent:
                if found is None or len(Path(stack.path).parts) > len(Path(found.path).parts):
                    found = stack
        return found


def location(workspace: Path) -> Path:
    """Where the file lives. One place, so it can be committed and found."""
    return Path(workspace) / DIRECTORY / FILE


def read(workspace: Path) -> Definitions:
    """Reads the stack file, or reports a workspace that has none.

    A workspace with no stack file is the ordinary case and not a problem —
    stacks are opt-in, and a rail full of complaints about their absence would
    be noise for everyone who has not adopted them.
    """
    path = location(workspace)
    if not path.is_file():
        return Definitions()
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as unreadable:
        return Definitions(problems=[Problem("", f"{path.name} cannot be read: {unreadable}")])
    except tomllib.TOMLDecodeError as broken:
        return Definitions(path=path, problems=[Problem("", f"{path.name} is not valid: {broken}")])
    return parse(document, path)


def parse(document: dict, path: Path | None = None) -> Definitions:
    """Turns a parsed file into stacks, keeping every problem it finds."""
    found: dict[str, Stack] = {}
    problems: list[Problem] = []

    declared = document.get("stacks")
    if not isinstance(declared, dict):
        return Definitions(path=path, problems=[Problem("", "no [stacks] table in the file")])

    for name, entry in declared.items():
        if not isinstance(entry, dict):
            problems.append(Problem(name, "is not a table"))
            continue
        where = entry.get("path")
        if not where:
            # A stack with no code location is not a deployable unit.
            problems.append(Problem(name, "has no path"))
            continue
        found[name] = Stack(
            name=name,
            path=str(where),
            engine=str(entry.get("engine", "tofu")),
            version=str(entry.get("version", "")),
            backend=str(entry.get("backend", "")),
            environment=str(entry.get("environment", "")),
            variables={str(k): str(v) for k, v in (entry.get("variables") or {}).items()},
            binding=Binding(
                account=str(entry.get("account", "")),
                role=str(entry.get("role", "")),
                region=str(entry.get("region", "")),
            ),
            outputs=tuple(str(value) for value in entry.get("outputs") or ()),
            needs={
                str(upstream): tuple(str(value) for value in values or ())
                for upstream, values in (entry.get("needs") or {}).items()
            },
        )

    problems.extend(_edge_problems(found))
    return Definitions(stacks=found, problems=problems, path=path)


def _edge_problems(stacks: dict[str, Stack]) -> list[Problem]:
    """FR-STK-03, at parse time.

    Consuming an output the producer does not expose is a validation error
    here, not a plan failure twenty minutes later.
    """
    problems: list[Problem] = []
    for stack in stacks.values():
        for upstream, wanted in sorted(stack.needs.items()):
            producer = stacks.get(upstream)
            if producer is None:
                problems.append(Problem(stack.name, f"needs {upstream}, which is not declared"))
                continue
            if upstream == stack.name:
                problems.append(Problem(stack.name, "needs itself"))
                continue
            for output in wanted:
                if output not in producer.outputs:
                    problems.append(
                        Problem(
                            stack.name,
                            f"consumes {upstream}.{output}, which {upstream} does not publish",
                        )
                    )
    return problems
