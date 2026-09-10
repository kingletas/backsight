"""Every engine command this application runs, read out of the application.

**Discovered, not listed.** A table of Terraform commands written by hand goes
stale the first time somebody adds one, and it goes stale silently — the table
still reads as complete. This walks the syntax tree of the package and reports
every argument list handed to the engine, so the answer is whatever the code
actually does today.

It is what the integration matrix is built from, and it is what a test asserts
against so that adding a command without testing it fails the build.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[2]

# What the engine binary is called where it is invoked. Both names are the same
# variable in different modules; a third would be a third place to look.
BINARIES = ("engine", "binary")


@dataclass(frozen=True)
class Invocation:
    """One argument list this application hands to the engine."""

    command: str
    arguments: tuple[str, ...]
    module: str
    line: int

    @property
    def where(self) -> str:
        return f"{self.module}:{self.line}"

    def __str__(self) -> str:
        return " ".join(("<engine>", self.command, *self.arguments))


def _literal(node: ast.AST) -> str | None:
    """One argument, when it is a literal. Anything computed is a placeholder."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr | ast.Call | ast.Name | ast.Attribute):
        return None
    return None


def _arguments(node: ast.List) -> tuple[str, tuple[str, ...]] | None:
    """The command and its literal arguments, or nothing when this is not one."""
    if not node.elts:
        return None
    first = node.elts[0]
    if not (isinstance(first, ast.Name) and first.id in BINARIES):
        return None
    said = [_literal(one) for one in node.elts[1:]]
    if not said or said[0] is None:
        return None
    # Anything computed — a path, an f-string — is reported as `<value>` rather
    # than dropped, because *that there is an argument here* is part of the
    # invocation even when what it holds is decided at run time.
    return said[0], tuple(one if one is not None else "<value>" for one in said[1:])


def found_in(package: Path | None = None) -> list[Invocation]:
    """Every engine invocation in the package, sorted by where it is."""
    where = Path(package or PACKAGE)
    found: list[Invocation] = []
    for path in sorted(where.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.List):
                continue
            read = _arguments(node)
            if read is None:
                continue
            command, arguments = read
            found.append(
                Invocation(
                    command=command,
                    arguments=arguments,
                    module=str(path.relative_to(where.parent)),
                    line=node.lineno,
                )
            )
    return sorted(found, key=lambda one: (one.command, one.module, one.line))


def commands(package: Path | None = None) -> list[str]:
    """The distinct engine subcommands this application runs."""
    return sorted({one.command for one in found_in(package)})
