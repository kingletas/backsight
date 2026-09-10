"""Evaluating a single expression against a workspace, through `tofu console`.

One process per expression, because the console exits on the first error and
would take every later expression with it — see
`docs/findings/004-the-console-stops-and-the-console-redacts.md`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backsight.engine.runner.process import Capture, RunTimedOut, capture

# The engine redacts sensitive values itself and the taint survives every
# function we tried. We recognise its marker so the interface can say why a
# value is missing, and we never try to redact anything ourselves.
REDACTED = "(sensitive value)"
UNAPPLIED = "(known after apply)"

# The console reports every error as line 1 of `<console-input>`, which is the
# line the person just typed. Repeating it back to them is noise.
_LOCATION = re.compile(r"^\s*on <console-input> line \d+:\n(?:.*\n)?", re.MULTILINE)
_SUMMARY = re.compile(r"^Error:\s*(.+)$", re.MULTILINE)

SECONDS = 30.0


@dataclass(frozen=True)
class Failure:
    """Why an expression produced no value."""

    summary: str
    detail: str

    @property
    def display(self) -> str:
        return f"{self.summary}\n{self.detail}".strip()


@dataclass(frozen=True)
class Evaluation:
    """One expression, and whatever came back."""

    expression: str
    value: str = ""
    failure: Failure | None = None
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.failure is None

    @property
    def redacted(self) -> bool:
        """True when the engine withheld the value because it is sensitive."""
        return REDACTED in self.value

    @property
    def unapplied(self) -> bool:
        """True when the value does not exist yet, rather than being unknown."""
        return UNAPPLIED in self.value


def evaluate(
    directory: Path,
    expression: str,
    *,
    binary: str = "tofu",
    seconds: float = SECONDS,
    run: object = None,
) -> Evaluation:
    """Evaluates one expression in `directory` and returns what came back.

    An empty expression is refused here rather than spawning a process to be
    told the same thing more slowly.
    """
    text = expression.strip()
    if not text:
        return Evaluation(
            expression=expression,
            failure=Failure(summary="Nothing to evaluate", detail="Type an expression first."),
        )

    runner = run if run is not None else capture
    try:
        result: Capture = runner(  # type: ignore[operator]
            [binary, "console", "-no-color"],
            cwd=directory,
            stdin=f"{text}\n",
            timeout=seconds,
        )
    except RunTimedOut as expired:
        return Evaluation(
            expression=text,
            failure=Failure(
                summary="The engine did not answer",
                detail=f"`{binary} console` was still running after {seconds:.0f}s.",
            ),
            seconds=expired.partial.seconds,
        )

    if result.ok:
        return Evaluation(expression=text, value=result.out.strip(), seconds=result.seconds)
    return Evaluation(
        expression=text,
        value=result.out.strip(),
        failure=_failure(result.err),
        seconds=result.seconds,
    )


def _failure(stderr: str) -> Failure:
    """Turns the engine's complaint into a summary and a body."""
    body = _LOCATION.sub("", stderr)
    found = _SUMMARY.search(body)
    summary = found.group(1).strip() if found else "The expression could not be evaluated"
    detail = _SUMMARY.sub("", body) if found else body
    return Failure(summary=summary, detail=_tidy(detail))


def _tidy(text: str) -> str:
    """Collapses the blank lines the engine's box drawing leaves behind."""
    lines = [line.rstrip() for line in text.strip().splitlines()]
    kept: list[str] = []
    for line in lines:
        if line or (kept and kept[-1]):
            kept.append(line)
    return "\n".join(kept).strip()
