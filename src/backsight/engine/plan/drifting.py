"""What changed outside Terraform, and where it changed.

Drift is the strongest thing this application can say, because it is true about
somebody's infrastructure whether or not the application is open. A number in a
status bar that goes nowhere is not that.

`tofu plan -refresh-only` is what asks. It reads every resource from the
provider and reports where reality no longer matches the state — a console edit,
another tool, an autoscaler doing its job. Nothing here changes anything: a
refresh-only plan is read-only by construction, which is what makes it safe to
run on a schedule.

The distinction that matters is drift that means something against drift that is
expected. An autoscaler moving a desired count is the system working; somebody
editing a security group by hand at two in the morning is not. This cannot tell
them apart on its own, so it says what changed and leaves the judgement where it
belongs — but it does put the attribute name in front of the person, which is
the part that lets them judge in a second rather than in an hour.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from backsight.engine.runner import process
from backsight.engine.runner.process import RunState

ENGINE = "tofu"
DEFAULT_TIMEOUT = 300.0

# Attributes every provider computes and nobody edited. Showing them as drift
# would bury the one line that matters under six that never mean anything.
NOISE = frozenset(
    {
        "id",
        "content_base64sha256",
        "content_base64sha512",
        "content_md5",
        "content_sha1",
        "content_sha256",
        "content_sha512",
    }
)


@dataclass(frozen=True)
class Difference:
    """One attribute that no longer says what the state says it says."""

    name: str
    was: object
    now: object

    def __str__(self) -> str:
        return f"{self.name}: {_short(self.was)} → {_short(self.now)}"


@dataclass(frozen=True)
class Drifted:
    """One resource reality has moved away from."""

    address: str
    action: str
    differences: tuple[Difference, ...] = ()

    @property
    def is_gone(self) -> bool:
        """The provider could not find it as Terraform recorded it.

        Narrower than "somebody deleted it", and deliberately so. The `local`
        provider reports a file whose contents were edited this way, because a
        file it no longer recognises is one it will make again. Saying "no
        longer exists" of a file sitting on disk would be this application
        inventing a meaning the engine did not give it.
        """
        return self.action == "delete"

    @property
    def summary(self) -> str:
        """One line, in the words somebody would use about their own estate."""
        if self.is_gone:
            return "no longer there as Terraform recorded it"
        if not self.differences:
            return "changed outside Terraform"
        named = ", ".join(difference.name for difference in self.differences[:3])
        more = len(self.differences) - 3
        return f"{named}{f' and {more} more' if more > 0 else ''} changed outside Terraform"


@dataclass
class Drift:
    """Everything that has moved, and whether the check could even run."""

    resources: tuple[Drifted, ...] = ()
    failure: str = ""
    checked: bool = False

    @property
    def count(self) -> int:
        return len(self.resources)

    @property
    def is_clean(self) -> bool:
        return self.checked and not self.failure and not self.resources

    @property
    def headline(self) -> str:
        """What the rail says. Silent when there is nothing to say."""
        if self.failure:
            return self.failure
        if not self.checked:
            return "Run a drift check to see what has changed outside Terraform"
        if not self.resources:
            return "Nothing has changed outside Terraform"
        gone = sum(1 for found in self.resources if found.is_gone)
        said = f"{self.count} resource{'' if self.count == 1 else 's'} changed outside Terraform"
        return f"{said}, {gone} of them no longer there" if gone else said


def _short(value: object) -> str:
    said = "nothing" if value is None else str(value)
    said = said.replace("\n", "⏎")
    return said if len(said) <= 40 else said[:37] + "…"


def drift_events(lines: Iterable[str]) -> list[dict]:
    """The `resource_drift` events in a `-json` stream."""
    found = []
    for line in lines:
        said = line.strip()
        if not said.startswith("{"):
            continue
        try:
            event = json.loads(said)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == "resource_drift":
            found.append(event)
    return found


def from_stream(lines: Iterable[str]) -> Drift:
    """What a refresh-only run said, read from the events alone.

    Enough for the count and the addresses. The attribute values live in the
    structured document, which is a second read of the same run.
    """
    resources = tuple(
        Drifted(
            address=str((event.get("change") or {}).get("resource", {}).get("addr", "")),
            action=str((event.get("change") or {}).get("action", "")),
        )
        for event in drift_events(lines)
    )
    return Drift(resources=resources, checked=True)


def from_document(document: dict) -> Drift:
    """The same run's plan document, which carries what actually differs."""
    resources = []
    for entry in document.get("resource_drift") or []:
        change = entry.get("change") or {}
        actions = change.get("actions") or []
        resources.append(
            Drifted(
                address=str(entry.get("address", "")),
                action=str(actions[0]) if actions else "update",
                differences=_differences(change.get("before"), change.get("after")),
            )
        )
    return Drift(resources=tuple(resources), checked=True)


def _differences(before: object, after: object) -> tuple[Difference, ...]:
    """Which attributes moved, ignoring the ones every provider computes."""
    if not isinstance(before, dict):
        return ()
    now = after if isinstance(after, dict) else {}
    found = [
        Difference(name=name, was=was, now=now.get(name))
        for name, was in sorted(before.items())
        if name not in NOISE and was != now.get(name)
    ]
    return tuple(found)


def check(
    directory: Path,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    engine: str = ENGINE,
    started=None,
) -> Drift:
    """Asks the engine what has moved. Changes nothing, by construction.

    A refresh-only plan is read-only, which is the whole reason this can be run
    without asking. It still costs a provider call per resource, so it is not
    run on every keystroke.
    """
    artifact = Path(directory) / ".backsight" / "drift.tfplan"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    running = process.start(
        [engine, "plan", "-refresh-only", "-input=false", "-out", str(artifact)],
        cwd=directory,
        timeout=timeout,
    )
    if started is not None:
        started(running)
    result = running.wait()
    if result.state is RunState.CANCELLED:
        return Drift(failure="")
    if not result.ok:
        return Drift(failure=_why(result.output))

    shown = process.start([engine, "show", "-json", str(artifact)], cwd=directory, timeout=timeout)
    if started is not None:
        started(shown)
    read = shown.wait()
    if not read.ok:
        return Drift(failure="The drift check ran but its result could not be read")
    try:
        document = json.loads(read.output)
    except ValueError:
        return Drift(failure="The drift check ran but its result could not be read")
    return from_document(document)


def _why(output: str) -> str:
    """The engine's first error line, or a sentence saying there is not one."""
    for line in output.splitlines():
        said = line.strip()
        if said.startswith("Error:"):
            return said[len("Error:") :].strip()
    return "The drift check could not run"
