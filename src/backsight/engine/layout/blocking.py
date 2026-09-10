"""What stops this workspace being useful, and which one to say first.

A blocking condition is not "important". It means **the application cannot do
its job until this is resolved** — no providers, no state, no plan. That was a
truncated red line at the bottom of the window, cut off mid-word, which is the
least prominent place on screen for the thing nothing works without.

One at a time, in the order they have to be cleared: an engine before an init,
an init before a backend, a backend before a plan. Two banners is a person
choosing which to read; the first one is the only one they can act on anyway.

Everything else is not this. A failed plan belongs in the drawer, a policy
failure in the review, drift in the inspector — those are things to know, and a
banner that says "important" of all of them says nothing of any.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Blocker(Enum):
    """The conditions that qualify, in the order they must be cleared."""

    NO_ENGINE = "no engine"
    NOT_INITIALISED = "not initialised"
    NO_BACKEND = "no backend"


@dataclass(frozen=True)
class Banner:
    """What one blocking condition says, and what to do about it."""

    blocker: Blocker
    title: str
    body: str
    action: str = ""
    command: str = ""
    icon: str = "dialog-warning-symbolic"
    # Only where the thing is still usable without resolving it. Initialisation
    # is not: dismissing it would hide the reason nothing works.
    dismissible: bool = False


# Written out rather than generated, because each one says what is wrong, what
# it prevents, and roughly how long the fix takes — and the third part is not
# something a template knows.
BANNERS = {
    Blocker.NO_ENGINE: Banner(
        blocker=Blocker.NO_ENGINE,
        title="OpenTofu is not installed",
        body=(
            "Backsight runs `tofu` for everything it knows. Nothing can plan, "
            "validate or format until it is on your PATH."
        ),
        action="How to install it",
        command="explain-engine",
        icon="dialog-error-symbolic",
    ),
    Blocker.NOT_INITIALISED: Banner(
        blocker=Blocker.NOT_INITIALISED,
        title="This workspace has not been initialised",
        body=(
            "Backsight cannot read providers or state until init runs. "
            "It usually takes about twenty seconds."
        ),
        action="Run init",
        command="initialise",
        icon="folder-download-symbolic",
    ),
}

# **Local state is not a banner, and this is where it stopped being one.**
#
# It is true on open, true all day, and true of every module in a repository
# that is a library rather than a deployment — twenty-seven of them in
# `~/Development/terraform`, none with a backend. A hundred and ten pixels
# across the top of the window, above the window controls, saying something
# nobody is going to act on before lunch, is the ungated signal this whole
# design is against: it is dismissed on reflex, and the banner that matters is
# dismissed on the same reflex a week later.
#
# So it is demoted to context on a signal that can indicate harm. It is a
# **file fact in the verdict line**, `local state`, which is where the other
# standing facts about this workspace already are and which is the size a
# standing fact deserves. It still opens the same explanation, and the apply
# gate still names it at the moment somebody is about to do the thing it is
# about.
LOCAL_STATE = "local state"


def first(*, engine_missing: bool, initialised: bool, has_backend: bool = True) -> Banner | None:
    """The one to show, or nothing.

    In the order the obstacles have to be cleared, because the second is not
    something anybody can act on while the first stands.

    **A banner is for something nothing works without.** `has_backend` is taken
    and ignored: local state stops nothing, so it is a fact in the verdict line
    rather than a strip across the top of the window — see `LOCAL_STATE`.
    """
    if engine_missing:
        return BANNERS[Blocker.NO_ENGINE]
    if not initialised:
        return BANNERS[Blocker.NOT_INITIALISED]
    return None
