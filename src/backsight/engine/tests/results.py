"""Reading what `tofu test -json` says, including what an assertion evaluated to.

The design argues that people abandon Terraform's test framework because *"a
failure prints 'assertion failed' with no values"*. That is true of the
human-readable output and **not true of the JSON**, which carries the evaluated
value of every expression the condition referenced:

    {"traversal": "terraform_data.nodes", "statement": "is tuple with 3 elements"}

So FR-TST-03 — the single behaviour the design says decides whether a test
framework is kept or abandoned — is a presentation problem rather than a data
one, and is far cheaper than the sheet assumes. This is the reader.

The stream is one JSON object per line, and an unrecognised type is ignored
rather than refused: the engine adds message types between versions, and a
reader that stops at the first unfamiliar one would break on an upgrade.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class Status(Enum):
    """How one run, file or whole suite ended."""

    # The names are past tense; the values are what the engine writes. A member
    # called PASS reads to a scanner as a hardcoded password, and PASSED is the
    # better name regardless.
    PASSED = "pass"
    FAILED = "fail"
    ERRORED = "error"
    SKIPPED = "skip"
    PENDING = "pending"

    @property
    def is_problem(self) -> bool:
        return self in (Status.FAILED, Status.ERRORED)


@dataclass(frozen=True)
class Value:
    """One expression an assertion referenced, and what it turned out to be."""

    expression: str
    was: str

    def __str__(self) -> str:
        return f"{self.expression} {self.was}"


@dataclass(frozen=True)
class Failure:
    """Why one run failed, with everything needed to show it in place."""

    summary: str
    detail: str
    path: str
    line: int
    condition: str = ""
    values: tuple[Value, ...] = ()

    @property
    def has_evidence(self) -> bool:
        """Whether the engine told us what the expressions actually were."""
        return bool(self.values)


@dataclass
class Run:
    """One `run` block."""

    name: str
    path: str
    status: Status = Status.PENDING
    failures: list[Failure] = field(default_factory=list)


@dataclass
class TestFile:
    """One `.tftest.hcl`, and the runs inside it."""

    path: str
    status: Status = Status.PENDING
    runs: list[Run] = field(default_factory=list)

    def run(self, name: str) -> Run | None:
        return next((r for r in self.runs if r.name == name), None)


@dataclass
class Results:
    """A whole test invocation."""

    files: list[TestFile] = field(default_factory=list)
    passed: int = 0
    failed: int = 0
    errored: int = 0
    skipped: int = 0
    status: Status = Status.PENDING

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errored + self.skipped

    def file(self, path: str) -> TestFile | None:
        return next((f for f in self.files if f.path == path), None)

    def all_runs(self) -> list[Run]:
        return [run for file in self.files for run in file.runs]

    def summary(self) -> str:
        """The line the status bar shows. Only what happened, never a zero."""
        said = [f"{self.passed} passed"]
        if self.failed:
            said.append(f"{self.failed} failed")
        if self.errored:
            said.append(f"{self.errored} errored")
        if self.skipped:
            said.append(f"{self.skipped} skipped")
        return " · ".join(said)


def _status(value: str | None) -> Status:
    try:
        return Status(value or "pending")
    except ValueError:
        return Status.PENDING


def parse(stream: str) -> Results:
    """Reads the whole JSON-lines stream into a tree."""
    results = Results()

    for line in stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            # A line that is not JSON is engine output, not a message.
            continue

        kind = record.get("type")
        if kind == "test_abstract":
            # The plan of what will run, before anything has. Building the tree
            # from this means the interface can show the shape immediately.
            for path, names in (record.get("test_abstract") or {}).items():
                results.files.append(
                    TestFile(path=path, runs=[Run(name=name, path=path) for name in names])
                )
        elif kind == "diagnostic":
            # A diagnostic names its own run and file, so it is attached by
            # name rather than by position. The engine emits it *after* the
            # `test_run` it belongs to, and relying on that order would break
            # the moment it stopped being true.
            found = _failure(record)
            if found is None:
                continue
            file = results.file(record.get("@testfile", ""))
            run = file.run(record.get("@testrun", "")) if file else None
            if run is not None:
                run.failures.append(found)
        elif kind == "test_run":
            body = record.get("test_run") or {}
            file = results.file(body.get("path", ""))
            run = file.run(body.get("run", "")) if file else None
            if run is not None:
                run.status = _status(body.get("status"))
        elif kind == "test_file":
            body = record.get("test_file") or {}
            file = results.file(body.get("path", ""))
            if file is not None:
                file.status = _status(body.get("status"))
        elif kind == "test_summary":
            body = record.get("test_summary") or {}
            results.passed = int(body.get("passed", 0))
            results.failed = int(body.get("failed", 0))
            results.errored = int(body.get("errored", 0))
            results.skipped = int(body.get("skipped", 0))
            results.status = _status(body.get("status"))
    return results


def _failure(record: dict) -> Failure | None:
    diagnostic = record.get("diagnostic") or {}
    if diagnostic.get("severity") != "error":
        return None
    where = diagnostic.get("range") or {}
    snippet = diagnostic.get("snippet") or {}
    return Failure(
        summary=diagnostic.get("summary", ""),
        detail=diagnostic.get("detail", ""),
        path=where.get("filename", record.get("@testfile", "")),
        line=int((where.get("start") or {}).get("line", 0)),
        condition=(snippet.get("code") or "").strip(),
        values=tuple(
            Value(expression=v.get("traversal", ""), was=v.get("statement", ""))
            for v in (snippet.get("values") or [])
        ),
    )
