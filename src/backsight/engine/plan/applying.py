"""Reading an apply as it happens, resource by resource.

Every Terraform tool goes quiet at the moment anxiety peaks: the apply runs,
logs scroll, and the person watches text they cannot act on. Then it ends and
they open the console by hand to find out whether it worked.

`tofu apply -json` says far more than the log does. It names each resource as it
starts, as it finishes, and as it fails, and the order is not the plan's order —
a replace arrives as a destroy early and a create much later, interleaved with
everything else. So progress is tracked **against the plan the person already
reviewed**, in that order, rather than as a stream.

The state that matters most is the one nobody designs for: an apply that stopped
part way. Some resources are changed, one failed, and the rest were never
reached — and those are three different situations for the person to be in.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from backsight.engine.plan.model import Action, Plan
from backsight.engine.runner import process
from backsight.engine.runner.process import RunState

ENGINE = "tofu"

# An apply is not a plan. It can take as long as it takes, and killing one part
# way is how a workspace ends up in a state nothing described.
DEFAULT_TIMEOUT = 3600.0


class Stage(Enum):
    """Where one resource has got to, in the words the screen uses."""

    WAITING = "waiting"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    # The apply stopped before it reached this one. Not a failure of its own,
    # and the distinction is the whole point: nothing was attempted here.
    NEVER_REACHED = "never reached"


# What each stage is called in front of somebody, per the kind of change. "Done"
# says nothing about whether a thing was made or removed.
DONE_WORDS = {
    Action.CREATE: "created",
    Action.UPDATE: "changed",
    Action.DELETE: "destroyed",
    Action.REPLACE: "replaced",
    Action.READ: "read",
    Action.NO_OP: "unchanged",
}

RUNNING_WORDS = {
    Action.CREATE: "creating",
    Action.UPDATE: "changing",
    Action.DELETE: "destroying",
    Action.REPLACE: "replacing",
    Action.READ: "reading",
    Action.NO_OP: "",
}


@dataclass
class Step:
    """One resource from the reviewed plan, and how far it has got."""

    address: str
    action: Action
    stage: Stage = Stage.WAITING
    seconds: float = 0.0
    detail: str = ""

    @property
    def word(self) -> str:
        """What to call its state, without making the reader translate."""
        if self.stage is Stage.DONE:
            return DONE_WORDS.get(self.action, "done")
        if self.stage is Stage.RUNNING:
            return RUNNING_WORDS.get(self.action, "running")
        if self.stage is Stage.FAILED:
            return "failed"
        if self.stage is Stage.NEVER_REACHED:
            return "never started"
        return "waiting"

    @property
    def changed_something(self) -> bool:
        """Whether real infrastructure moved. A replace that got half way did."""
        return self.stage in (Stage.DONE, Stage.FAILED)


@dataclass
class Progress:
    """Every resource in the plan, and what has become of it so far."""

    steps: list[Step] = field(default_factory=list)
    finished: bool = False
    failure: str = ""

    @property
    def by_address(self) -> dict[str, Step]:
        return {step.address: step for step in self.steps}

    @property
    def done(self) -> int:
        return sum(1 for step in self.steps if step.stage is Stage.DONE)

    @property
    def failed(self) -> list[Step]:
        return [step for step in self.steps if step.stage is Stage.FAILED]

    @property
    def never_reached(self) -> list[Step]:
        return [step for step in self.steps if step.stage is Stage.NEVER_REACHED]

    @property
    def ok(self) -> bool:
        return self.finished and not self.failed

    @property
    def is_partial(self) -> bool:
        """Some of it happened and some of it did not.

        The situation with no good name in any other tool, and the one somebody
        most needs described rather than logged.
        """
        return bool(self.failed) and any(step.changed_something for step in self.steps)


def steps_for(plan: Plan) -> list[Step]:
    """The plan's own changes, in the order the person read them."""
    return [
        Step(address=change.address, action=change.action)
        for change in plan.changes
        if change.action is not Action.NO_OP
    ]


def read_events(lines: Iterable[str]) -> Iterator[dict]:
    """The JSON objects in the stream, skipping anything that is not one.

    A line that will not parse is not a failure. `tofu` writes plain text to the
    same stream when something goes wrong early, and losing the whole apply
    because of one unparseable line would be worse than ignoring it.
    """
    for line in lines:
        said = line.strip()
        if not said.startswith("{"):
            continue
        try:
            found = json.loads(said)
        except ValueError:
            continue
        if isinstance(found, dict):
            yield found


def _address(event: dict) -> str:
    hook = event.get("hook") or {}
    resource = hook.get("resource") or {}
    if resource.get("addr"):
        return str(resource["addr"])
    change = event.get("change") or {}
    return str((change.get("resource") or {}).get("addr", ""))


def apply_event(progress: Progress, event: dict) -> None:
    """One event, folded into what is known so far.

    A replace arrives as two events against one address — a destroy and then a
    create — so a completed destroy must not mark a replacement done. It stays
    running until the create completes.
    """
    kind = event.get("type")
    if kind == "diagnostic" and event.get("@level") == "error":
        detail = (event.get("diagnostic") or {}).get("summary") or event.get("@message", "")
        progress.failure = progress.failure or str(detail)
        return
    if kind == "change_summary":
        progress.finished = True
        _never_reached(progress)
        return

    step = progress.by_address.get(_address(event))
    if step is None:
        return
    if kind == "apply_start":
        step.stage = Stage.RUNNING
        return
    if kind == "apply_complete":
        elapsed = (event.get("hook") or {}).get("elapsed_seconds")
        step.seconds = float(elapsed) if isinstance(elapsed, int | float) else step.seconds
        if step.action is Action.REPLACE and _is_a_destroy(event):
            # Half of a replace. The create has not happened yet.
            return
        step.stage = Stage.DONE
        return
    if kind in ("apply_errored", "provision_errored"):
        step.stage = Stage.FAILED
        step.detail = str(event.get("@message", ""))
        progress.failure = progress.failure or step.detail
        _never_reached(progress)


def _is_a_destroy(event: dict) -> bool:
    """Whether this completion was the destroy half of a replacement."""
    return "Destruction complete" in str(event.get("@message", ""))


def _never_reached(progress: Progress) -> None:
    """Anything still waiting once the apply has stopped was never attempted.

    Said explicitly because "waiting" and "never started" are different things
    to be told about your infrastructure, and only one of them is over.
    """
    if not progress.failure and not progress.finished:
        return
    for step in progress.steps:
        if step.stage is Stage.WAITING:
            step.stage = Stage.NEVER_REACHED


def follow(plan: Plan, lines: Iterable[str]) -> Progress:
    """A whole stream, folded. For a capture on disk and for the tests."""
    progress = Progress(steps=steps_for(plan))
    for event in read_events(lines):
        apply_event(progress, event)
    if not progress.finished and progress.failure:
        _never_reached(progress)
    return progress


def keep(directory: Path, outcome: ApplyOutcome, *, home: Path | None = None) -> Path | None:
    """Writes what an apply printed, beside a note of what it did.

    FR-ST-04. It streams and it is readable and it is gone when the window
    closes, which makes "what did that apply actually say" a question with no
    answer an hour later. Kept per workspace, newest last, and never on the
    workspace itself — an apply log is this machine's record, not something to
    commit.
    """
    where = _kept(home) / _safe(str(directory))
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    try:
        where.mkdir(parents=True, exist_ok=True)
        path = where / f"{stamp}.log"
        path.write_text(
            "\n".join(
                [
                    f"# {stamp} — {outcome.progress.done} of {len(outcome.progress.steps)}",
                    *[f"# {step.address}: {step.word}" for step in outcome.progress.steps],
                    "",
                    outcome.output,
                ]
            ),
            encoding="utf-8",
        )
    except OSError:
        # Losing the record must never lose the apply.
        return None
    return path


def kept_for(directory: Path, *, home: Path | None = None) -> list[Path]:
    """Every apply log for one workspace, oldest first."""
    where = _kept(home) / _safe(str(directory))
    return sorted(where.glob("*.log")) if where.is_dir() else []


def _kept(home: Path | None) -> Path:
    if home is not None:
        return Path(home) / ".local" / "state" / "backsight" / "applies"
    root = os.environ.get("XDG_STATE_HOME")
    base = Path(root) if root else Path.home() / ".local" / "state"
    return base / "backsight" / "applies"


def _safe(said: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "-", said).strip("-")[:120] or "workspace"


@dataclass(frozen=True)
class ApplyOutcome:
    """What the apply did, and everything it left behind."""

    progress: Progress
    output: str
    state: RunState
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.state is RunState.SUCCEEDED and self.progress.ok


def run(
    directory: Path,
    artifact: Path,
    *,
    on_step: Callable[[Progress], None] | None = None,
    plan: Plan,
    timeout: float = DEFAULT_TIMEOUT,
    engine: str = ENGINE,
    started: Callable[[object], None] | None = None,
) -> ApplyOutcome:
    """Applies a reviewed plan artifact, reporting each resource as it moves.

    The artifact rather than the configuration, always: applying the
    configuration would run whatever it says now, which is not the thing anybody
    approved.
    """
    progress = Progress(steps=steps_for(plan))

    def line(said: str) -> None:
        for event in read_events([said]):
            apply_event(progress, event)
        if on_step is not None:
            on_step(progress)

    running = process.start(
        [engine, "apply", "-json", "-input=false", "-auto-approve", str(artifact)],
        cwd=directory,
        timeout=timeout,
        on_line=line,
    )
    if started is not None:
        started(running)
    result = running.wait()
    if not progress.finished:
        _never_reached(progress)
    return ApplyOutcome(
        progress=progress,
        output=result.output,
        state=result.state,
        seconds=result.seconds,
    )
