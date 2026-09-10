"""The rail shows the graph, its problems, and what a change reaches."""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk  # noqa: E402

from backsight.app.stacks_rail import HOW_TO, IN_A_CYCLE, StacksRail  # noqa: E402
from backsight.engine.stacks.graph import consumers_of, radius_of_change  # noqa: E402
from backsight.engine.stacks.model import Definitions, read  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "stacks"
PLAIN = read(ROOT / "plain")
CYCLIC = read(ROOT / "cyclic")
BROKEN = read(ROOT / "broken")


def labels(widget) -> list[str]:
    found: list[str] = []
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Label):
            found.append(child.get_label())
        found.extend(labels(child))
        child = child.get_next_sibling()
    return found


def test_a_workspace_with_no_stacks_says_how_to_declare_them():
    """An undeclared graph is the ordinary case, not a fault."""
    rail = StacksRail()
    rail.show(Definitions())
    assert HOW_TO in labels(rail)


def test_every_stack_reaches_the_rail_in_apply_order():
    rail = StacksRail()
    rail.show(PLAIN)
    shown = labels(rail)
    assert shown.index("network") < shown.index("data") < shown.index("api") < shown.index("edge")


def test_a_stack_in_a_cycle_is_marked_as_one():
    rail = StacksRail()
    rail.show(CYCLIC)
    assert IN_A_CYCLE in labels(rail)


def test_the_cycle_itself_is_named_on_the_rail():
    """A count would tell nobody which stacks to look at."""
    rail = StacksRail()
    rail.show(CYCLIC)
    assert any(said.startswith("Cycle: ") and "one" in said for said in labels(rail))


def test_every_problem_is_shown_rather_than_counted():
    rail = StacksRail()
    rail.show(BROKEN)
    shown = labels(rail)
    assert any("does not publish" in said for said in shown)
    assert any("is not declared" in said for said in shown)


def test_a_broken_file_still_shows_the_stacks_that_are_fine():
    rail = StacksRail()
    rail.show(BROKEN)
    assert "good" in labels(rail)


def test_the_radius_says_why_each_stack_is_in_it():
    rail = StacksRail()
    rail.show(PLAIN, consumers_of(PLAIN, "network"))
    shown = labels(rail)
    assert "consumes network.private_subnets, vpc_id" in shown
    assert "consumes api.api_url" in shown


def test_a_stack_outside_the_radius_shows_where_it_lives_instead():
    rail = StacksRail()
    rail.show(PLAIN, radius_of_change(PLAIN, "network", ()))
    assert "prod" in labels(rail)


def test_clicking_a_stack_reaches_the_caller():
    opened: list[str] = []
    rail = StacksRail(on_open=lambda stack: opened.append(stack.name))
    rail.show(PLAIN)
    _first_button(rail).emit("clicked")
    assert opened == ["network"]


def test_a_stacks_tooltip_carries_everything_it_declares():
    rail = StacksRail()
    rail.show(PLAIN)
    tip = _first_button(rail).get_tooltip_text()
    assert "infra/network" in tip
    assert "publishes vpc_id" in tip


def test_redrawing_replaces_rather_than_appends():
    rail = StacksRail()
    rail.show(PLAIN)
    rail.show(PLAIN)
    assert labels(rail).count("network") == 1


def _first_button(widget) -> Gtk.Button:
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Button):
            return child
        found = _first_button(child)
        if found is not None:
            return found
        child = child.get_next_sibling()
    return None


def test_the_environment_reaches_the_switcher():
    """Which environment a change is aimed at belongs in front of you.

    It was the header's subtitle; the header is a workspace switcher now, and
    `prod` is the environment that earns a chip.
    """
    from backsight.app.window import Window

    window = Window()
    window.open_workspace(ROOT / "plain")
    window.open_file(ROOT / "plain" / "infra" / "network" / "main.tf")
    known = window._known_workspace()
    assert known is not None
    assert known.environment == "prod"


def test_a_stack_that_states_no_region_gets_no_invented_one():
    """A plausible guess is how somebody applies to the wrong account."""
    from backsight.app.stacks_rail import StacksRail

    rail = StacksRail()
    rail.show(CYCLIC)
    assert not any("eu-" in said for said in labels(rail))


def test_opening_a_stack_with_no_terraform_in_it_says_so():
    from backsight.app.window import Window

    window = Window()
    window.open_workspace(ROOT / "cyclic")
    said: list[str] = []
    window._say = said.append
    window.open_stack(CYCLIC.get("alone"))
    assert said and "no Terraform in it" in said[0]
