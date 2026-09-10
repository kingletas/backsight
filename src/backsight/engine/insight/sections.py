"""What each analysis section says, derived from one plan rather than four.

The first critical fix: **"2 to add" above "Needs a plan" reads as a
broken application.** Every dependent section takes its state from the same
plan object, so the panel can no longer disagree with its own headline.

The second half of that fix matters as much: when a plan exists and a section
still has nothing, it says **why it in particular** has nothing. "Needs a plan"
when a plan is right there is worse than silence, because it is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class State(Enum):
    """Why a section is empty, or that it is not."""

    WAITING = "waiting"
    UNAVAILABLE = "unavailable"
    READY = "ready"


@dataclass(frozen=True)
class Section:
    """One section of the analysis rail."""

    title: str
    state: State
    detail: str

    @property
    def is_empty(self) -> bool:
        return self.state is not State.READY


@dataclass(frozen=True)
class Capabilities:
    """What this installation can currently do, as distinct from what it has."""

    policy_set: bool = False
    credentials: bool = False
    container_runtime: bool = False
    pricing_data: bool = False
    convergence_run: bool = False
    # What the last scan and the last estimate actually said, so the rail can
    # carry the answer rather than a caption about there not being one.
    policy_said: str = ""
    cost_said: str = ""


# An empty state is an invitation, not a status report. "Needs a plan" tells
# somebody they failed to do something; each of these says what goes here, why
# it is empty, and the one action that fills it.
COST_WAITING = "Run a plan to see how this changes your bill"
ACCESS_WAITING = "Run a plan to see what becomes reachable from the internet"


# Cost, policy and public access are three readings of one plan, so before
# there is a plan they are one absence rather than three. A rail that opens as
# a column of separate apologies reads as an application with four broken
# features instead of one thing not done yet.
NO_PLAN_YET = "No plan yet. Run one to see cost, policy, public access, and drift."

# Drift is the exception, and it is a different kind of empty: it is not
# waiting on a plan, it is missing a dependency. Collapsing it into the others
# would hide the one thing here somebody has to go and install.
# Two different things were both called "Drift check". This one runs the plan
# against a local emulator in a container, which is a rehearsal — it says
# nothing about whether reality has moved. Drift is a refresh-only plan, needs
# no container at all, and now owns the name.
REHEARSAL = "Rehearsal"

# What this concept is called, everywhere it is named — the tab, the chip, the
# gutter mark and the view. The plainer "public access" reads better as a verb
# and survives in the menu item, but it cannot be counted, and the verdict line
# has to say "1 exposure" in a chip that is 24 pixels tall.
EXPOSURE = "Exposure"


@dataclass(frozen=True)
class Rail:
    """The analysis rail: one panel about the plan, and drift beneath it."""

    waiting: str
    sections: list[Section]
    drift: Section

    @property
    def has_plan(self) -> bool:
        return not self.waiting


def rail(plan: object | None, can: Capabilities) -> Rail:
    """What the rail shows, as one panel rather than four cards."""
    found = describe(plan, can)
    drift = next(section for section in found if section.title == REHEARSAL)
    about_plan = [section for section in found if section.title != REHEARSAL]
    if plan is None:
        return Rail(waiting=NO_PLAN_YET, sections=[], drift=drift)
    return Rail(waiting="", sections=about_plan, drift=drift)


def describe(plan: object | None, can: Capabilities) -> list[Section]:
    """Every section, from one plan and one statement of what is available."""
    planned = plan is not None
    return [
        _cost(planned, can),
        _policy(planned, can),
        _exposure(planned, can),
        _convergence(can),
    ]


def _cost(planned: bool, can: Capabilities) -> Section:
    if not planned:
        return Section("Monthly cost", State.WAITING, COST_WAITING)
    if can.cost_said:
        return Section("Monthly cost", State.READY, can.cost_said)
    if not can.pricing_data:
        # The distinction that matters: no pricing data, not no plan.
        return Section(
            "Monthly cost",
            State.UNAVAILABLE,
            "No prices imported yet, so nothing can be estimated",
        )
    return Section("Monthly cost", State.READY, "")


def _policy(planned: bool, can: Capabilities) -> Section:
    if can.policy_said:
        return Section("Policy checks", State.READY, can.policy_said)
    if not can.policy_set:
        # True whether or not a plan exists, and it is the thing to fix first.
        return Section(
            "Policy checks",
            State.UNAVAILABLE,
            "No policies configured. Add a policy set in Preferences.",
        )
    if not planned:
        return Section(
            "Policy checks", State.WAITING, "Run a plan to check it against your policies"
        )
    return Section("Policy checks", State.READY, "")


def _exposure(planned: bool, can: Capabilities) -> Section:
    # The menu says "Analyse public access" on purpose — that phrase is how
    # somebody who has never met the word finds this. The concept is Exposure.
    if not planned:
        return Section(EXPOSURE, State.WAITING, ACCESS_WAITING)
    if not can.credentials:
        return Section(
            EXPOSURE,
            State.UNAVAILABLE,
            "Tracing what is reachable needs access to the account",
        )
    return Section(EXPOSURE, State.READY, "")


def _convergence(can: Capabilities) -> Section:
    """Trying the plan against a local copy before the real thing."""
    if not can.container_runtime:
        return Section(
            REHEARSAL,
            State.UNAVAILABLE,
            "Trying a plan against a local copy needs Docker or Podman. "
            "Install either one to enable it.",
        )
    if not can.convergence_run:
        return Section(
            REHEARSAL,
            State.WAITING,
            "Try this plan against a local copy before running it for real",
        )
    return Section(REHEARSAL, State.READY, "")


# Why apply cannot run, in the order the obstacles have to be cleared. The
# status bar and the button both read this, because a greyed primary action
# and a status line that disagree read as a bug.
NEEDS_PLAN = "Run a plan before applying"
NEEDS_CREDENTIALS = "Credentials are needed to apply"
NOTHING_TO_DO = "This plan changes nothing"


# The engine's own provider. A plan made only of its resources reaches nothing
# outside the machine it runs on, so it needs no credentials — which is what
# lets the example workspace demonstrate an apply rather than describe one.
#
# Matched on the `builtin` namespace rather than on a list of hosts: a real plan
# document says `terraform.io/builtin/terraform`, and a list written from memory
# had three plausible spellings and not that one.
BUILT_IN_NAMESPACE = "/builtin/"


def needs_credentials(plan: object | None) -> bool:
    """Whether applying this plan would reach anything outside this machine.

    Read from the plan rather than assumed. Requiring credentials for every
    apply meant the one workspace that can be applied here — the offline
    example — could never be applied, so the product could never show its own
    ending to anybody trying it.
    """
    changes = [
        change
        for change in getattr(plan, "changes", ())
        if getattr(change, "action", None) is not None
    ]
    if not changes:
        return False
    return any(not _is_built_in(change) for change in changes)


def _is_built_in(change: object) -> bool:
    """Whether this resource belongs to the engine rather than to a provider."""
    said = str(getattr(change, "provider", "") or "")
    name = said.split('["')[-1].rstrip('"]') if '["' in said else said
    return name == "terraform" or BUILT_IN_NAMESPACE in name


def why_apply_is_blocked(plan: object | None, can: Capabilities, changes: int = 1) -> str | None:
    """The one sentence explaining a greyed Apply, or None when it is live."""
    if plan is None:
        return NEEDS_PLAN
    if changes == 0:
        return NOTHING_TO_DO
    if needs_credentials(plan) and not can.credentials:
        return NEEDS_CREDENTIALS
    return None
