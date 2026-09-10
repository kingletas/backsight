"""Validate, format and initialise, as the engine actually reports them.

Captured output is in `fixtures/commands/`. Two things about it decide the
shape here:

- **`fmt -check` exits 3**, not 1, when files need formatting. Treating a
  non-zero exit as failure would report a tidy-up as a broken workspace.
- **`validate -json` gives a location per diagnostic**, so a problem can be
  shown on the line it is on rather than in a wall of output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from backsight.engine.runner.process import Capture, RunTimedOut, capture

SECONDS = 120.0

# `fmt -check` uses 3 for "these files are not formatted". It is not an error.
UNFORMATTED = 3


@dataclass(frozen=True)
class Problem:
    """One thing validate found, and where."""

    severity: str
    summary: str
    detail: str = ""
    path: str = ""
    line: int = 0

    @property
    def is_error(self) -> bool:
        return self.severity == "error"

    @property
    def where(self) -> str:
        return f"{self.path}:{self.line}" if self.path and self.line else ""


@dataclass(frozen=True)
class Validation:
    """What validate said."""

    valid: bool
    problems: list[Problem] = field(default_factory=list)
    output: str = ""

    @property
    def errors(self) -> list[Problem]:
        return [problem for problem in self.problems if problem.is_error]

    def summary(self) -> str:
        """Only counts that are not zero. Nothing reads as a row of negatives."""
        errors = len(self.errors)
        warnings = len(self.problems) - errors
        said = []
        if errors:
            said.append(f"{errors} error{'' if errors == 1 else 's'}")
        if warnings:
            said.append(f"{warnings} warning{'' if warnings == 1 else 's'}")
        return " · ".join(said) if said else "Valid"


@dataclass(frozen=True)
class Formatting:
    """Which files are not formatted, and the diff that would fix them."""

    files: tuple[str, ...] = ()
    diff: str = ""

    @property
    def tidy(self) -> bool:
        return not self.files

    def summary(self) -> str:
        if self.tidy:
            return "Already formatted"
        count = len(self.files)
        return f"{count} file{'' if count == 1 else 's'} would change"


def validate(directory: Path, *, binary: str = "tofu", run=None) -> Validation:
    """Runs `validate -json` and reads what it found."""
    result = _run(run, [binary, "validate", "-json"], directory)
    if result is None:
        return Validation(valid=False, output="The engine did not answer")
    try:
        document = json.loads(result.out)
    except json.JSONDecodeError:
        # Validate refuses to run at all when the workspace is not initialised,
        # and says so on stderr in prose. That is a real answer, not a crash.
        return Validation(valid=False, output=(result.err or result.out).strip())
    return Validation(
        valid=bool(document.get("valid")),
        problems=[_problem(entry) for entry in document.get("diagnostics") or []],
        output=result.out,
    )


def formatting(directory: Path, *, binary: str = "tofu", run=None) -> Formatting:
    """Asks which files are not formatted, and changes nothing."""
    result = _run(run, [binary, "fmt", "-check", "-diff", "-no-color"], directory)
    if result is None:
        return Formatting()
    if result.returncode not in (0, UNFORMATTED):
        return Formatting()
    files = tuple(
        line.strip()
        for line in result.out.splitlines()
        if line.strip() and not line.startswith(("-", "+", "@", " "))
    )
    return Formatting(files=files, diff=result.out)


def initialise(directory: Path, *, binary: str = "tofu", run=None) -> Capture | None:
    """Runs `init`. Backends and providers are the engine's business, not ours."""
    return _run(run, [binary, "init", "-no-color", "-input=false"], directory)


@dataclass(frozen=True)
class Formatted:
    """What formatting one buffer produced, or why it produced nothing."""

    text: str = ""
    complaint: str = ""

    @property
    def ok(self) -> bool:
        return not self.complaint

    @property
    def changed_anything(self) -> bool:
        return bool(self.text)


def format_text(
    text: str, *, directory: Path | None = None, binary: str = "tofu", run=None
) -> Formatted:
    """Formats one buffer through `fmt -`, which reads stdin and writes stdout.

    A file that will not parse is left exactly as it is, and the engine's own
    complaint is handed back. Formatting is the one operation nobody expects to
    change what their code means, so a partial result is never written.
    """
    runner = run if run is not None else capture
    try:
        result = runner(
            [binary, "fmt", "-no-color", "-"], cwd=directory, stdin=text, timeout=SECONDS
        )
    except RunTimedOut:
        return Formatted(complaint="Formatting did not finish")
    if result.returncode != 0:
        return Formatted(complaint=(result.err or result.out).strip() or "Formatting failed")
    return Formatted(text="" if result.out == text else result.out)


def _run(run, command: list[str], directory: Path) -> Capture | None:
    runner = run if run is not None else capture
    try:
        return runner(command, cwd=directory, timeout=SECONDS)
    except RunTimedOut:
        return None


def _problem(entry: dict) -> Problem:
    where = entry.get("range") or {}
    start = where.get("start") or {}
    return Problem(
        severity=entry.get("severity", "error"),
        summary=entry.get("summary", ""),
        detail=entry.get("detail", ""),
        path=where.get("filename", ""),
        line=int(start.get("line", 0)),
    )


@dataclass(frozen=True)
class State:
    """What the state file says is out there."""

    resources: tuple[str, ...] = ()
    output: str = ""
    empty_because: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.resources

    def summary(self) -> str:
        if self.resources:
            count = len(self.resources)
            return f"{count} resource{'' if count == 1 else 's'} in state"
        return self.empty_because or "Nothing in state"


def state(directory: Path, *, binary: str = "tofu", run=None) -> State:
    """Reads the state through the engine rather than the file.

    `tofu show -json` is the supported reading; parsing `terraform.tfstate` by
    hand would be reading a format nobody promised us. With no state at all it
    returns `{"format_version": "1.0"}` and nothing else, which is a fact
    rather than a failure.
    """
    result = _run(run, [binary, "show", "-json"], directory)
    if result is None:
        return State(empty_because="The engine did not answer")
    try:
        document = json.loads(result.out)
    except json.JSONDecodeError:
        return State(empty_because=(result.err or result.out).strip() or "State could not be read")
    values = (document.get("values") or {}).get("root_module") or {}
    found = _addresses(values)
    return State(
        resources=tuple(found),
        output=result.out,
        empty_because="" if found else "Nothing has been applied from this workspace yet",
    )


def _addresses(module: dict) -> list[str]:
    """Every resource address in state, this module and the ones it calls."""
    found = [
        resource.get("address", "")
        for resource in module.get("resources") or []
        if resource.get("address")
    ]
    for child in module.get("child_modules") or []:
        found.extend(_addresses(child))
    return sorted(found)
