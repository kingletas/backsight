"""Every chip in the verdict line opens something.

**A number that goes nowhere is not a finding**, and a chip that opens the
drawer and then says "there is no such tab" is worse: it looked clickable, it
was clicked, and the answer was about the application rather than about the
plan.
"""

from __future__ import annotations

import pytest

from backsight.engine.presentation.status import build

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


@pytest.fixture
def window():
    from backsight.app.offscreen import use_a_private_display
    from backsight.app.window import Window

    use_a_private_display()
    return Window()


def everything() -> list[str]:
    """One line with every chip it can have on it at once."""
    line = build(
        planned=True,
        counts={"create": 1, "update": 1, "replace": 1, "delete": 1},
        cost="$1/mo",
        cost_direction="↑",
        exposures=1,
        coverage=9,
        tests=(1, 2),
        drifted=1,
        stale_stacks=1,
        waiting_stacks=2,
        unformatted=True,
        branch="main",
    )
    said = [s.action for s in line.verdict + line.chips + line.facts if s.action]
    said.append(build(blocked="broken", problems=2).verdict[0].action)
    return said


def test_every_chip_reaches_a_real_surface(window):
    tabs = {name.lower() for name in window._drawer.sections}
    unrouted = [
        action
        for action in everything()
        if action.lower() not in tabs
        and action.lower() not in window.ELSEWHERE
        and window.AS_A_TAB.get(action.lower(), "").lower() not in tabs
    ]
    assert unrouted == [], "chips that open nothing: " + ", ".join(unrouted)


def test_opening_one_never_says_there_is_no_such_tab(window):
    for action in everything():
        window.open_drawer(action)
        assert "There is no" not in " ".join(str(said) for said in window.activity[-1:])
