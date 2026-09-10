"""The path is the evidence, and a partial answer says it is partial."""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk  # noqa: E402

from backsight.app.exposure_panel import MARKS, NOTHING, TONES, ExposurePanel  # noqa: E402
from backsight.engine.insight.exposure import Finding, Hop, Reach, Report  # noqa: E402

EXPOSED = Finding(
    address="aws_db_instance.orders",
    reach=Reach.EXPOSED,
    path=(
        Hop("0.0.0.0/0", "the rule allows every source"),
        Hop("sg.db", "the group carries that rule"),
        Hop("igw-4f2c", "the route table reaches the gateway"),
    ),
)
UNDECIDED = Finding(
    address="aws_lb.public",
    reach=Reach.UNKNOWN,
    detail="the security group is created outside this configuration",
)


def labels(widget) -> list[str]:
    found: list[str] = []
    child = widget.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Label):
            found.append(child.get_label())
        found.extend(labels(child))
        child = child.get_next_sibling()
    return found


def test_every_reach_has_a_shape_of_its_own():
    assert len(set(MARKS.values())) == len(MARKS)
    assert set(MARKS) == set(TONES) == set(Reach)


def test_an_exposed_resource_and_its_path_both_reach_the_screen():
    panel = ExposurePanel()
    panel.show(Report(findings=[EXPOSED]))
    shown = labels(panel)
    assert "aws_db_instance.orders" in shown
    assert "0.0.0.0/0 → sg.db → igw-4f2c" in shown


def test_the_reason_for_each_hop_survives_the_compression():
    """One line on screen, the whole evidence on the tooltip — FR-EXP-06."""
    panel = ExposurePanel()
    panel.show(Report(findings=[EXPOSED]))
    tips = _tooltips(panel)
    assert any("the route table reaches the gateway" in tip for tip in tips)


def test_a_plan_that_exposes_nothing_says_so_rather_than_showing_a_blank():
    panel = ExposurePanel()
    panel.show(Report(findings=[Finding("aws_instance.api", Reach.NOT_EXPOSED)]))
    assert NOTHING in labels(panel)


def test_an_undecided_finding_is_shown_rather_than_dropped():
    """Silently omitting what we could not decide is how you get a wrong answer."""
    panel = ExposurePanel()
    panel.show(Report(findings=[UNDECIDED]))
    shown = labels(panel)
    assert "aws_lb.public" in shown
    assert "1 undecided" in shown


def test_a_partial_report_says_why_it_is_partial():
    panel = ExposurePanel()
    panel.show(Report(findings=[EXPOSED], partial=True, partial_because=("no account access",)))
    assert "no account access" in labels(panel)


def test_exposed_is_listed_before_undecided():
    panel = ExposurePanel()
    panel.show(Report(findings=[UNDECIDED, EXPOSED]))
    shown = labels(panel)
    assert shown.index("aws_db_instance.orders") < shown.index("aws_lb.public")


def test_the_waiting_state_carries_the_sentence_it_is_given():
    """The rail and the drawer read the same source; neither owns the wording."""
    panel = ExposurePanel()
    panel.waiting("Needs account access to trace reachability")
    assert "Needs account access to trace reachability" in labels(panel)


def _tooltips(widget) -> list[str]:
    found: list[str] = []
    child = widget.get_first_child()
    while child is not None:
        tip = child.get_tooltip_text()
        if tip:
            found.append(tip)
        found.extend(_tooltips(child))
        child = child.get_next_sibling()
    return found
