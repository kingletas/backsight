"""Reading the state back after an apply, and saying whether it matches.

"Applied" is not "working". Every Terraform tool stops at the moment the command
exits, and the person then opens a console by hand to find out whether what they
asked for is actually there. That last step is what turns dread into relief, and
it is the one nobody builds.

This is the honest half of it: re-read the state the apply just wrote and check
that each resource the plan intended is there, or gone, as intended. It is not a
health check and does not claim to be one — a `terraform_data` resource has
nothing to be healthy about, and for a real provider the difference between
"recorded in state" and "serving traffic" is exactly the gap this must not
pretend to close. It says which of the two it checked.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from backsight.engine.plan.model import Action, Plan

STATE = "terraform.tfstate"


@dataclass(frozen=True)
class Check:
    """One resource, and whether the state agrees with what was asked for."""

    address: str
    expected: str
    found: str

    @property
    def agrees(self) -> bool:
        return self.expected == self.found


@dataclass
class Verification:
    """What the state says, once the apply has finished."""

    checks: tuple[Check, ...] = ()
    unreadable: str = ""

    @property
    def disagreements(self) -> tuple[Check, ...]:
        return tuple(check for check in self.checks if not check.agrees)

    @property
    def ok(self) -> bool:
        return not self.unreadable and not self.disagreements

    @property
    def summary(self) -> str:
        """One sentence, and it never says more than it checked."""
        if self.unreadable:
            return f"The state could not be read back: {self.unreadable}"
        if not self.checks:
            return "Nothing to check against the state"
        if self.ok:
            count = len(self.checks)
            return (
                f"All {count} resource{'' if count == 1 else 's'} are recorded in the state "
                "as the plan intended"
            )
        missing = len(self.disagreements)
        return f"{missing} resource{'' if missing == 1 else 's'} did not end up as the plan said"


# What the state should say about a resource, per what the plan asked for.
EXPECTED = {
    Action.CREATE: "present",
    Action.UPDATE: "present",
    Action.REPLACE: "present",
    Action.READ: "present",
    Action.DELETE: "gone",
    Action.NO_OP: "present",
}


def addresses_in(document: dict) -> set[str]:
    """Every managed resource the state file records, by address.

    Written against the real shape rather than the documented one: a resource
    with `count` or `for_each` has instances under it, and its address in a plan
    carries the key.
    """
    found: set[str] = set()
    for resource in document.get("resources") or []:
        if resource.get("mode") != "managed":
            continue
        parts = (resource.get("module"), resource.get("type"), resource.get("name"))
        prefix = ".".join(part for part in parts if part)
        for instance in resource.get("instances") or [{}]:
            key = instance.get("index_key")
            if key is None:
                found.add(prefix)
            elif isinstance(key, int):
                found.add(f"{prefix}[{key}]")
            else:
                found.add(f'{prefix}["{key}"]')
    return found


def read_state(directory: Path) -> dict | None:
    """The state file beside the configuration, or None when there is none."""
    path = Path(directory) / STATE
    if not path.is_file():
        return None
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def verify(plan: Plan, directory: Path, *, state: dict | None = None) -> Verification:
    """Whether the state now says what the plan said it would.

    A local state file only. A remote backend's state is not beside the
    configuration, and reading it means the credentials this does not have — so
    it says it could not check rather than guessing that everything is fine.
    """
    document = state if state is not None else read_state(directory)
    if document is None:
        return Verification(unreadable="no local state file to read")

    present = addresses_in(document)
    checks = tuple(
        Check(
            address=change.address,
            expected=EXPECTED[change.action],
            found="present" if change.address in present else "gone",
        )
        for change in plan.changes
        if change.action is not Action.NO_OP
    )
    return Verification(checks=checks)
