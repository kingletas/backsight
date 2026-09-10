"""An apply that did not finish, found on the next launch.

FR-ST-05. A Terraform apply that is killed part-way leaves the state file and
the real world in a relationship nobody knows. The one thing that must not
happen next is a silent re-plan: a plan against a state that may be wrong
produces a confident answer about a situation nobody has looked at.

So this records that an apply began, notices on the next launch that it never
ended, and hands the person the steps. It does not reconcile anything itself.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from backsight.engine.actor import Actor

# Local to one workspace and to one machine. Deliberately not one of the stable
# formats §12 of the BRD asks v1 to keep for the companion service — this
# records that something is unfinished here, not what happened.
MARKER = Path(".backsight") / "apply-in-progress.json"
FORMAT = 1


@dataclass(frozen=True)
class Interrupted:
    """An apply that started and never reported an ending."""

    workspace: Path
    started_at: datetime
    plan_digest: str
    actor: str
    process_id: int
    output_path: Path | None = None

    @property
    def still_running(self) -> bool:
        """Whether the process that began it is somehow still alive.

        A running apply is not an interrupted one, and telling somebody their
        state is indeterminate while it is being changed would be worse than
        saying nothing.
        """
        try:
            os.kill(self.process_id, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def guidance(self) -> list[str]:
        """What to do, in order. None of it happens automatically."""
        return [
            "An apply started and never reported finishing, so the state file and "
            "your infrastructure may not agree.",
            f"It began at {self.started_at:%Y-%m-%d %H:%M} UTC on plan {self.plan_digest}.",
            "Read the apply output from that run before anything else.",
            "Run a refresh-only plan to see what the state now believes.",
            "Compare that against what the apply had already done.",
            "Nothing has been re-planned or reconciled for you, and nothing will be "
            "until you say so.",
        ]


def begin(
    workspace: Path, *, plan_digest: str, actor: Actor, output_path: Path | None = None
) -> Path:
    """Records that an apply is starting. Called before the process is launched."""
    marker = Path(workspace) / MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        json.dumps(
            {
                "format": FORMAT,
                "started_at": datetime.now(UTC).isoformat(),
                "plan_digest": plan_digest,
                "actor": actor.responsible,
                "process_id": os.getpid(),
                "output_path": str(output_path) if output_path else None,
            },
            indent=2,
        )
        + "\n"
    )
    return marker


def finish(workspace: Path) -> None:
    """Records that the apply ended, however it ended.

    A failed apply is a finished one: it reported what happened. Only an apply
    nobody heard the end of is indeterminate.
    """
    marker = Path(workspace) / MARKER
    marker.unlink(missing_ok=True)


def interrupted(workspace: Path) -> Interrupted | None:
    """The unfinished apply in this workspace, if there is one."""
    marker = Path(workspace) / MARKER
    if not marker.is_file():
        return None
    try:
        recorded = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # A half-written marker is still evidence that something started.
        return Interrupted(
            workspace=Path(workspace),
            started_at=datetime.fromtimestamp(marker.stat().st_mtime, UTC),
            plan_digest="unknown",
            actor="unknown",
            process_id=-1,
        )
    output = recorded.get("output_path")
    return Interrupted(
        workspace=Path(workspace),
        started_at=datetime.fromisoformat(recorded["started_at"]),
        plan_digest=recorded.get("plan_digest", "unknown"),
        actor=recorded.get("actor", "unknown"),
        process_id=int(recorded.get("process_id", -1)),
        output_path=Path(output) if output else None,
    )
