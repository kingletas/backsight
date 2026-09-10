"""Reachability across the projected graph, and what it refuses to decide."""

import json
from pathlib import Path

import pytest

from backsight.engine.insight.exposure import Reach, analyse
from backsight.engine.insight.graph import project

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "fixtures" / "exposure"


def load(name: str):
    return project(json.loads((CORPUS / name / "plan.json").read_text()))


def report_for(name: str):
    return analyse(load(name))


def finding(name: str, address: str):
    return next(f for f in report_for(name).findings if f.address == address)


# --- the graph ------------------------------------------------------------


def test_the_graph_holds_everything_that_will_exist_not_only_what_changed():
    graph = load("open-to-the-internet")
    assert len(graph.nodes) == 7
    assert {n.type for n in graph.nodes.values()} >= {
        "aws_vpc",
        "aws_subnet",
        "aws_route_table",
        "aws_internet_gateway",
        "aws_security_group",
        "aws_network_interface",
    }


def test_edges_come_from_references_because_ids_are_unknown_at_plan_time():
    graph = load("open-to-the-internet")
    subnets = graph.targets_of("aws_network_interface.db", via="subnet_id")
    assert [n.address for n in subnets] == ["aws_subnet.public"]
    groups = graph.targets_of("aws_network_interface.db", via="security_groups")
    assert [n.address for n in groups] == ["aws_security_group.db"]


def test_a_variable_reference_is_not_an_edge():
    graph = load("incomplete-graph")
    assert graph.targets_of("aws_network_interface.db", via="subnet_id") == []


# --- reachability ---------------------------------------------------------


def test_an_open_rule_on_a_routed_subnet_is_reachable():
    assert finding("open-to-the-internet", "aws_network_interface.db").reach is Reach.EXPOSED


def test_the_same_rule_with_no_route_out_is_not_reachable():
    """The difference existing scanners miss, because it is not in the rule."""
    found = finding("private-subnet-no-route", "aws_network_interface.db")
    assert found.reach is Reach.NOT_EXPOSED
    assert "nothing routes to the subnet" in found.detail


def test_a_public_subnet_with_a_narrow_rule_is_not_reachable():
    found = finding("narrow-cidr-on-a-public-subnet", "aws_network_interface.db")
    assert found.reach is Reach.NOT_EXPOSED
    assert "admits the whole internet" in found.detail


def test_the_ipv6_form_of_the_open_rule_is_caught():
    """`::/0` is the same door, and is missed by anything matching only the v4 form."""
    assert finding("ipv6-open", "aws_network_interface.db").reach is Reach.EXPOSED


def test_an_open_group_attached_to_nothing_produces_no_finding():
    assert report_for("open-but-no-interface").findings == []


# --- evidence -------------------------------------------------------------


def test_every_exposure_carries_its_path_hop_by_hop():
    """FR-EXP-06: verifiable without trusting this code."""
    evidence = finding("open-to-the-internet", "aws_network_interface.db").evidence()
    assert len(evidence) == 6
    assert evidence[0].startswith("0.0.0.0/0")
    assert "aws_internet_gateway.main" in evidence[1]
    assert "aws_route_table.public" in evidence[2]
    assert "aws_subnet.public" in evidence[3]
    assert "aws_security_group.db" in evidence[4]
    assert evidence[-1].startswith("aws_network_interface.db")


def test_a_resource_that_is_not_reachable_carries_no_path():
    assert finding("private-subnet-no-route", "aws_network_interface.db").path == ()


# --- incompleteness -------------------------------------------------------


def test_a_subnet_from_outside_the_configuration_cannot_be_decided():
    """FR-EXP-08. Saying "not exposed" here is the silent false negative."""
    found = finding("incomplete-graph", "aws_network_interface.db")
    assert found.reach is Reach.UNKNOWN
    assert found.is_exposed is False
    assert "not in this configuration" in found.detail


def test_an_incomplete_analysis_never_reads_as_a_clean_one():
    report = report_for("incomplete-graph")
    assert report.partial is True
    assert "incomplete" in report.headline()
    assert "Nothing newly reachable" not in report.headline()


def test_a_complete_analysis_with_nothing_found_says_so_plainly():
    report = report_for("private-subnet-no-route")
    assert report.partial is False
    assert report.headline() == "Nothing newly reachable from the internet"


def test_the_reason_for_partiality_is_named():
    report = report_for("incomplete-graph")
    assert "aws_network_interface.db" in report.partial_because


# --- accuracy, and what this corpus can and cannot establish ---------------


def test_the_analyser_agrees_with_every_recorded_answer():
    """The measured rate on this corpus, with what it means stated below."""
    wrong = []
    for directory in sorted(d for d in CORPUS.iterdir() if (d / "case.json").is_file()):
        spec = json.loads((directory / "case.json").read_text())
        found = {f.address: f for f in analyse(load(directory.name)).findings}
        for expectation in spec["expects"]:
            got = found.get(expectation["resource"])
            if got is None:
                continue
            answer = True if got.is_exposed else None if got.is_partial else False
            if answer != expectation["exposed"]:
                wrong.append(
                    (directory.name, expectation["resource"], expectation["exposed"], answer)
                )
    assert wrong == [], wrong


@pytest.mark.xfail(
    reason=(
        "NFR-12 asks for a false-positive rate under 5% and a false-negative rate "
        "under 1%. Six cases, all written and checked by the same hand that wrote "
        "the analyser, cannot establish either number — the corpus would agree with "
        "any analyser built from it. This is marked failing on purpose so the claim "
        "is never quietly assumed. It needs a corpus of real configurations with "
        "answers verified by somebody else."
    ),
    strict=True,
)
def test_the_accuracy_targets_are_established():
    raise AssertionError("no accuracy claim can be made from a self-authored corpus")
