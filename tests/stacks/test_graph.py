"""Cycles, apply order and blast radius, from declared edges alone."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.stacks.graph import (
    consumers_of,
    cycles,
    order,
    radius_of_change,
    stacks_in_order,
)
from backsight.engine.stacks.model import read

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "stacks"
PLAIN = read(ROOT / "plain")
CYCLIC = read(ROOT / "cyclic")


def test_a_graph_with_no_loops_has_no_cycles():
    assert cycles(PLAIN) == []


def test_a_cycle_is_named_rather_than_merely_detected():
    """ "There is a cycle" is not actionable — FR-STK-04."""
    found = cycles(CYCLIC)
    assert len(found) == 1
    said = str(found[0])
    assert said.count("→") == 3
    for name in ("one", "two", "three"):
        assert name in said


def test_the_same_cycle_is_not_reported_once_per_stack_in_it():
    assert len(cycles(CYCLIC)) == 1


def test_a_stack_that_needs_itself_is_a_cycle():
    assert any("needs_itself" in str(cycle) for cycle in cycles(read(ROOT / "broken")))


def test_apply_order_puts_every_stack_after_what_it_needs():
    """FR-STK-08."""
    placed = order(PLAIN)
    assert placed.index("network") < placed.index("data")
    assert placed.index("data") < placed.index("api")
    assert placed.index("api") < placed.index("edge")


def test_a_stack_in_a_cycle_is_left_out_of_the_order():
    """An order that quietly includes a cycle is an order somebody will follow."""
    placed = order(CYCLIC)
    assert placed == ["alone"]


def test_stacks_left_out_of_the_order_are_still_listed():
    """They exist; the rail must show them even though they cannot be ordered."""
    named = [stack.name for stack in stacks_in_order(CYCLIC)]
    assert named[0] == "alone"
    assert sorted(named) == ["alone", "one", "three", "two"]


def test_every_downstream_stack_is_found_nearest_first():
    found = consumers_of(PLAIN, "network")
    assert [consumer.name for consumer in found.consumers] == ["api", "data", "edge"]
    assert found.direct == [c for c in found.consumers if c.name in ("api", "data")]


def test_a_consumer_says_which_edge_put_it_there():
    """Beyond the first hop the outputs belong to a different stack."""
    found = radius_of_change(PLAIN, "network", ("vpc_id",))
    by_name = {consumer.name: consumer for consumer in found.consumers}
    assert by_name["data"].because() == "consumes network.vpc_id"
    assert by_name["api"].because() == "consumes data.database_endpoint"
    assert by_name["edge"].because() == "consumes api.api_url"


def test_only_the_consumers_of_the_outputs_a_change_touches_are_direct():
    """FR-STK-06: which of those outputs this change touches."""
    found = radius_of_change(PLAIN, "network", ("vpc_id",))
    assert [c.name for c in found.direct] == ["data"]
    # api consumes private_subnets from network, which this change did not touch.
    assert found.consumers[1].distance == 2


def test_a_change_touching_no_published_output_reaches_nothing():
    """The difference between a blast radius and a permanent warning."""
    found = radius_of_change(PLAIN, "network", ())
    assert found.is_empty
    assert found.summary() == "Nothing downstream consumes this"


def test_the_last_stack_in_the_chain_has_nothing_downstream():
    assert consumers_of(PLAIN, "edge").is_empty


def test_a_stack_nobody_declared_has_an_empty_radius():
    assert consumers_of(PLAIN, "not_a_stack").is_empty


def test_the_summary_counts_direct_and_further_separately():
    assert consumers_of(PLAIN, "network").summary() == "2 downstream · 1 further on"


def test_a_cycle_does_not_hang_the_radius():
    """Walking a loop forever is the obvious way to get this wrong."""
    assert not consumers_of(CYCLIC, "one").is_empty
