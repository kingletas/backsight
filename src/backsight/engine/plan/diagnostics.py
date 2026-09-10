"""Reading the engine's own errors out of its output.

The panel used to say "the plan failed; the output says why" and then show the
output nowhere. That is the worst of both: it admits an explanation exists and
withholds it.

Terraform and OpenTofu print diagnostics in a fixed shape — a summary line, an
optional source location, and a body — so the summary can be lifted out and put
in front of somebody while the whole text stays one click away. **The raw
output is never replaced by this.** A translation nobody can check against the
original is just a different opacity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# `Error: <summary>` at the start of a line, after the box drawing is stripped.
HEADING = re.compile(r"^(Error|Warning):\s*(.+?)\s*$", re.MULTILINE)

# `  on main.tf line 2, in resource "terraform_data" "a":`
WHERE = re.compile(r"^\s*on (?P<path>\S+) line (?P<line>\d+)", re.MULTILINE)

# Everything the engine draws around a diagnostic, which is noise once it has
# been read into fields.
BOX = re.compile(r"^[│╷╵]\s?", re.MULTILINE)

# The engine says this itself, and it names the command. Recognised because it
# is the first failure almost everybody meets and there is a button for it.
NEEDS_INIT = re.compile(r"\b(tofu|terraform) init\b")


@dataclass(frozen=True)
class Diagnostic:
    """One thing the engine complained about."""

    severity: str
    summary: str
    detail: str = ""
    path: str = ""
    line: int = 0
    raw: str = ""

    @property
    def is_error(self) -> bool:
        return self.severity == "Error"

    @property
    def where(self) -> str:
        return f"{self.path}:{self.line}" if self.path and self.line else ""

    def __str__(self) -> str:
        return f"{self.summary} ({self.where})" if self.where else self.summary


def read(output: str) -> list[Diagnostic]:
    """Every diagnostic in some engine output, in the order it printed them."""
    text = BOX.sub("", output or "")
    found: list[Diagnostic] = []
    matches = list(HEADING.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        where = WHERE.search(body)
        found.append(
            Diagnostic(
                severity=match.group(1),
                summary=match.group(2),
                detail=_detail(body),
                path=where.group("path") if where else "",
                line=int(where.group("line")) if where else 0,
                raw=text[match.start() : end].rstrip(),
            )
        )
    return found


def errors(output: str) -> list[Diagnostic]:
    return [found for found in read(output) if found.is_error]


def summarise(output: str) -> str:
    """One line naming what went wrong, or nothing when nothing was said.

    Never invents a reason. Output the engine produced in a shape this does not
    recognise is left to the raw text rather than guessed at.
    """
    found = errors(output)
    if not found:
        return ""
    first = str(found[0])
    if len(found) == 1:
        return first
    return f"{first} · and {len(found) - 1} more"


def needs_initialising(output: str) -> bool:
    """Whether the engine is asking to be initialised.

    It is the first failure almost everybody meets, and the fix is one command
    the application already knows how to run.
    """
    return bool(errors(output)) and bool(NEEDS_INIT.search(output or ""))


def _detail(body: str) -> str:
    """The prose, without the location line or the quoted source."""
    lines = []
    for line in body.splitlines():
        if WHERE.match(line):
            continue
        # The engine echoes the offending source under the location, indented
        # and numbered. The editor already shows that file.
        if re.match(r"^\s*\d+:", line):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()
