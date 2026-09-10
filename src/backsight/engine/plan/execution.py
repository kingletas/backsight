"""Running a plan, without the window waiting on it.

Two steps, because Terraform has two: `plan -out` writes a binary artifact, and
`show -json` renders it. Only the artifact may be applied later (FR-ST-03), so
the file is kept rather than the JSON being re-derived from a second run.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from backsight.engine.plan import diagnostics
from backsight.engine.plan.model import Plan, parse
from backsight.engine.runner import process
from backsight.engine.runner.process import Result, RunState

# `tofu` is the engine. Terraform is detected, never bundled — BRD R-1.
ENGINE = "tofu"

# A plan on a cold provider cache can take a while; past this something is wrong.
DEFAULT_TIMEOUT = 300.0


@dataclass(frozen=True)
class PlanOutcome:
    """What running a plan produced, including when it produced nothing."""

    plan: Plan | None
    artifact: Path | None
    output: str
    state: RunState
    seconds: float
    # The raw document, because hints and traces read parts of it the model
    # deliberately does not carry — configuration references, planned values.
    document: dict | None = None

    @property
    def ok(self) -> bool:
        return self.plan is not None

    @property
    def failure(self) -> str | None:
        """One line saying what went wrong, or nothing when it did not.

        It used to say "the output says why" and show the output nowhere,
        which is the worst of both: it admits an explanation exists and
        withholds it.
        """
        if self.ok:
            return None
        if self.state is RunState.TIMED_OUT:
            return f"The plan did not finish in {self.seconds:.0f}s"
        if self.state is RunState.CANCELLED:
            return "The plan was cancelled"
        return diagnostics.summarise(self.output) or "The plan failed"

    @property
    def diagnostics(self) -> list[diagnostics.Diagnostic]:
        """Everything the engine complained about, in the order it said it."""
        return diagnostics.read(self.output)

    @property
    def errors(self) -> list[diagnostics.Diagnostic]:
        """What stopped the plan. Warnings never do."""
        return diagnostics.errors(self.output)

    @property
    def warnings(self) -> list[diagnostics.Diagnostic]:
        """What the engine wants noticed, none of which stopped anything."""
        return [found for found in self.diagnostics if not found.is_error]

    @property
    def needs_initialising(self) -> bool:
        """Whether the engine is asking to be initialised.

        The first failure almost everybody meets, and the fix is one command
        the application already knows how to run.
        """
        return diagnostics.needs_initialising(self.output)


def speculative(
    directory: Path,
    *,
    artifact: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    on_line: Callable[[str], None] | None = None,
    engine: str = ENGINE,
    started: Callable[[object], None] | None = None,
) -> PlanOutcome:
    """Plans a directory and reads the result back.

    Read-only against real current state, which is what makes it speculative:
    it refreshes and compares, and changes nothing.

    `started` is handed the running process. Without it there was no way to
    reach one: this started and waited in a single expression, so cancelling a
    plan discarded the answer and left `tofu` running — holding the state lock,
    for a run nobody was waiting for.
    """
    artifact = artifact or (directory / ".backsight" / "speculative.tfplan")
    artifact.parent.mkdir(parents=True, exist_ok=True)

    planning = process.start(
        [engine, "plan", "-no-color", "-input=false", "-out", str(artifact)],
        cwd=directory,
        timeout=timeout,
        on_line=on_line,
    )
    if started is not None:
        started(planning)
    written = planning.wait()
    if not written.ok:
        return _failed(written, artifact=None)

    reading = process.start(
        [engine, "show", "-json", str(artifact)], cwd=directory, timeout=timeout
    )
    if started is not None:
        started(reading)
    shown = reading.wait()
    if not shown.ok:
        return _failed(shown, artifact=artifact)

    try:
        document = json.loads(shown.output)
    except json.JSONDecodeError:
        # A plan that ran and produced something unreadable is a failure with a
        # different cause than one that did not run, and saying so saves an hour.
        return PlanOutcome(
            plan=None,
            artifact=artifact,
            output=f"{written.output}\nthe plan JSON could not be read",
            state=RunState.FAILED,
            seconds=written.seconds + shown.seconds,
        )

    return PlanOutcome(
        plan=parse(document),
        artifact=artifact,
        output=written.output,
        state=RunState.SUCCEEDED,
        seconds=written.seconds + shown.seconds,
        document=document,
    )


def _failed(result: Result, artifact: Path | None) -> PlanOutcome:
    return PlanOutcome(
        plan=None,
        artifact=artifact,
        output=result.output,
        state=result.state,
        seconds=result.seconds,
    )
