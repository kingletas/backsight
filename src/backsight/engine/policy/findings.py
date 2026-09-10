"""Policy findings, from the scanners that are actually installed.

**Severity drives presentation, not enforcement** — FR-POL-03. This is a desktop
application and it cannot stop a determined person from running `tofu apply` in
a terminal, so pretending to be a gate would be a claim it cannot keep. It says
what a policy set found, at the line that caused it, and lets somebody decide.

A finding carries its line, which is the difference between something the gutter
can point at and a line in a report nobody opens.

Checkov's output has two shapes and they are not the same shape with a different
count: a run with findings is a **list** of check-type blocks, and a run with
none is a **single object**. A reader written against either one alone finds
nothing for the other, silently.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from backsight.engine.runner import process
from backsight.engine.runner.process import RunState

CHECKOV = "checkov"
DEFAULT_TIMEOUT = 300.0


class Severity(Enum):
    """How much attention a finding is asking for."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unrated"

    @property
    def tone(self) -> str:
        """Which consequence colour it takes. Never the only carrier."""
        return {
            Severity.HIGH: "irreversible",
            Severity.MEDIUM: "disruptive",
            Severity.LOW: "safe",
            Severity.UNKNOWN: "disruptive",
        }[self]


@dataclass(frozen=True)
class Finding:
    """One thing a policy set objected to, and where."""

    rule: str
    title: str
    resource: str = ""
    path: str = ""
    line: int = 0
    severity: Severity = Severity.UNKNOWN
    guide: str = ""
    source: str = "checkov"

    @property
    def where(self) -> str:
        name = Path(self.path).name if self.path else ""
        return f"{name}:{self.line}" if name and self.line else name

    @property
    def summary(self) -> str:
        """One line, with the rule last — it is how you look it up, not what
        it says."""
        said = self.title
        if self.resource:
            said = f"{self.resource} — {said}"
        return said


@dataclass
class Report:
    """Everything a scan found, and whether it could run at all."""

    findings: tuple[Finding, ...] = ()
    passed: int = 0
    scanner: str = ""
    failure: str = ""
    ran: bool = False

    @property
    def count(self) -> int:
        return len(self.findings)

    @property
    def is_clean(self) -> bool:
        return self.ran and not self.failure and not self.findings

    def at(self, path: Path) -> list[Finding]:
        """Everything about one file, for the gutter."""
        wanted = Path(path).name
        return [one for one in self.findings if Path(one.path).name == wanted]

    @property
    def by_severity(self) -> dict[Severity, int]:
        found: dict[Severity, int] = {}
        for one in self.findings:
            found[one.severity] = found.get(one.severity, 0) + 1
        return found

    @property
    def headline(self) -> str:
        """What the rail says. It never claims to have stopped anything."""
        if self.failure:
            return self.failure
        if not self.ran:
            return "No policy set configured. Install checkov to scan this workspace."
        if not self.findings:
            return "Nothing found by the policies that ran"
        high = self.by_severity.get(Severity.HIGH, 0)
        said = f"{self.count} finding{'' if self.count == 1 else 's'}"
        return f"{said}, {high} high" if high else said


def _blocks(document) -> list[dict]:
    """The check-type blocks, whichever shape the run came back in.

    A run with findings is a list of them and a run with none is a single
    object. Measured, because the two are not the same shape with a different
    count and a reader written against one silently finds nothing for the other.
    """
    if isinstance(document, list):
        return [one for one in document if isinstance(one, dict)]
    return [document] if isinstance(document, dict) else []


def _severity(said) -> Severity:
    try:
        return Severity(str(said).lower())
    except (ValueError, AttributeError):
        return Severity.UNKNOWN


def read_checkov(text: str) -> Report:
    """One scan's output, in either of its shapes."""
    try:
        document = json.loads(text)
    except ValueError:
        return Report(scanner=CHECKOV, failure="The policy scan produced nothing readable")

    found: list[Finding] = []
    passed = 0
    for block in _blocks(document):
        results = block.get("results") or {}
        passed += len(results.get("passed_checks") or [])
        for failure in results.get("failed_checks") or []:
            lines = failure.get("file_line_range") or [0, 0]
            found.append(
                Finding(
                    rule=str(failure.get("check_id", "")),
                    title=str(failure.get("check_name", "")),
                    resource=str(failure.get("resource", "")),
                    path=str(failure.get("file_path", "")),
                    line=int(lines[0]) if lines else 0,
                    severity=_severity(failure.get("severity")),
                    guide=str(failure.get("guideline") or ""),
                )
            )
    return Report(findings=tuple(found), passed=passed, scanner=CHECKOV, ran=True)


def scan(
    directory: Path,
    *,
    scanner: str = CHECKOV,
    timeout: float = DEFAULT_TIMEOUT,
    started=None,
) -> Report:
    """Runs whichever scanner is installed. Absence is a state, not a failure."""
    running = process.start(
        [scanner, "-d", str(directory), "-o", "json", "--compact", "--quiet"],
        cwd=directory,
        timeout=timeout,
    )
    if started is not None:
        started(running)
    result = running.wait()
    if result.state is RunState.CANCELLED:
        return Report(scanner=scanner)
    if not result.output.strip():
        return Report(
            scanner=scanner,
            failure=f"{scanner} is not installed, so nothing was scanned",
        )
    return read_checkov(result.output)


def suppressed(findings: Iterable[Finding], rules: Iterable[str]) -> tuple[Finding, ...]:
    """Everything left after the rules somebody has already ruled on.

    FR-POL-04. A suppression is recorded in the workspace so it travels with
    the code and is reviewable in the pull request, rather than living in one
    person's editor where nobody else can see what was waved through.
    """
    ignored = {said.strip() for said in rules if said.strip()}
    return tuple(one for one in findings if one.rule not in ignored)
