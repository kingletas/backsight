"""Whether a change makes something reachable from the internet.

FR-EXP-02 and FR-EXP-06. The question is not "is this rule 0.0.0.0/0" — that is
what existing scanners answer, and it is why they miss exposure that emerges
from a new rule meeting a subnet that was already public. The question is
whether a path exists, and every finding carries that path hop by hop so a
reviewer can check it without trusting this code.

**Incompleteness is a first-class answer.** A resource whose subnet is a literal
id from outside the configuration cannot be decided here, and saying "not
exposed" about it would be the silent false negative FR-EXP-08 calls worse than
a false positive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backsight.engine.insight.graph import Graph, Node

# The doors. `::/0` is the same door as `0.0.0.0/0` and is missed by anything
# that only matches the v4 spelling.
OPEN_TO_THE_WORLD = ("0.0.0.0/0", "::/0")

# An id written as a literal rather than built from a reference. Anything
# matching this names something outside the configuration.
EXTERNAL_PREFIXES = ("subnet-", "vpc-", "sg-", "rtb-", "igw-", "eni-")


class Reach(Enum):
    """What can be said about one resource."""

    EXPOSED = "reachable from the internet"
    NOT_EXPOSED = "not reachable from the internet"
    UNKNOWN = "cannot be decided from this configuration"


@dataclass(frozen=True)
class Hop:
    """One step of a path, in the words a reviewer reads."""

    address: str
    because: str

    def __str__(self) -> str:
        return f"{self.address} — {self.because}"


@dataclass(frozen=True)
class Finding:
    """One resource, what can be said about it, and the evidence."""

    address: str
    reach: Reach
    path: tuple[Hop, ...] = ()
    detail: str = ""

    @property
    def is_exposed(self) -> bool:
        return self.reach is Reach.EXPOSED

    @property
    def is_partial(self) -> bool:
        return self.reach is Reach.UNKNOWN

    def evidence(self) -> list[str]:
        """The path, hop by hop. FR-EXP-06: verifiable without trusting us."""
        return [str(hop) for hop in self.path]


@dataclass
class Report:
    """Everything the analysis found, and whether it could see the whole picture."""

    findings: list[Finding] = field(default_factory=list)
    partial: bool = False
    partial_because: tuple[str, ...] = ()

    @property
    def exposed(self) -> list[Finding]:
        return [f for f in self.findings if f.is_exposed]

    @property
    def undecided(self) -> list[Finding]:
        return [f for f in self.findings if f.is_partial]

    def headline(self) -> str:
        """Never a clean bill of health on an incomplete picture."""
        if self.partial:
            return (
                f"{len(self.exposed)} newly reachable · analysis incomplete"
                if self.exposed
                else "Analysis incomplete — some resources could not be decided"
            )
        if not self.exposed:
            return "Nothing newly reachable from the internet"
        return f"{len(self.exposed)} newly reachable from the internet"


def _is_external(value: object) -> bool:
    return isinstance(value, str) and value.startswith(EXTERNAL_PREFIXES)


def _open_rules(group: Node) -> list[dict]:
    """Ingress rules that admit the whole internet."""
    found = []
    for rule in group.value("ingress") or []:
        if not isinstance(rule, dict):
            continue
        cidrs = list(rule.get("cidr_blocks") or []) + list(rule.get("ipv6_cidr_blocks") or [])
        if any(cidr in OPEN_TO_THE_WORLD for cidr in cidrs):
            found.append(rule)
    return found


def _route_tables_for(graph: Graph, subnet: Node) -> list[Node]:
    """The route tables associated with a subnet, through its associations."""
    tables = []
    for association in graph.of_type("aws_route_table_association"):
        subnets = graph.targets_of(association.address, via="subnet_id")
        if any(s.address == subnet.address for s in subnets):
            tables.extend(graph.targets_of(association.address, via="route_table_id"))
    return tables


def _reaches_the_internet(graph: Graph, table: Node) -> bool:
    """Whether a route table sends the default route at an internet gateway."""
    for route in table.value("route") or []:
        if not isinstance(route, dict):
            continue
        if route.get("cidr_block") not in OPEN_TO_THE_WORLD:
            if route.get("ipv6_cidr_block") not in OPEN_TO_THE_WORLD:
                continue
        # A gateway id resolved from a reference is unknown at plan time, so the
        # edge is what says which gateway it is.
        gateways = [
            node
            for node in graph.targets_of(table.address, via="route")
            if node.type == "aws_internet_gateway"
        ]
        if gateways:
            return True
    return False


def analyse(graph: Graph) -> Report:
    """Every network interface, and whether the internet can reach it."""
    report = Report()
    incomplete: set[str] = set()

    for interface in graph.of_type("aws_network_interface"):
        groups = graph.targets_of(interface.address, via="security_groups")
        subnets = graph.targets_of(interface.address, via="subnet_id")

        if not subnets and _is_external(interface.value("subnet_id")):
            incomplete.add(interface.address)
            report.findings.append(
                Finding(
                    address=interface.address,
                    reach=Reach.UNKNOWN,
                    detail=(
                        f"{interface.address} sits in "
                        f"{interface.value('subnet_id')}, which is not in this "
                        "configuration, so nothing here can say whether it routes "
                        "to the internet."
                    ),
                )
            )
            continue

        opened = [(group, rule) for group in groups for rule in _open_rules(group)]
        if not opened:
            report.findings.append(
                Finding(
                    address=interface.address,
                    reach=Reach.NOT_EXPOSED,
                    detail="No attached group admits the whole internet.",
                )
            )
            continue

        path = _path_to(graph, interface, subnets, opened)
        if path is None:
            report.findings.append(
                Finding(
                    address=interface.address,
                    reach=Reach.NOT_EXPOSED,
                    detail=(
                        "A group admits the whole internet, but nothing routes to "
                        "the subnet from outside."
                    ),
                )
            )
            continue

        report.findings.append(Finding(address=interface.address, reach=Reach.EXPOSED, path=path))

    report.partial = bool(incomplete) or graph.is_partial
    report.partial_because = tuple(sorted(incomplete | graph.unresolved))
    return report


def _path_to(graph: Graph, interface: Node, subnets: list[Node], opened) -> tuple[Hop, ...] | None:
    """The hops from the internet to this interface, or nothing if there are none."""
    for subnet in subnets:
        for table in _route_tables_for(graph, subnet):
            if not _reaches_the_internet(graph, table):
                continue
            gateways = [
                node
                for node in graph.targets_of(table.address, via="route")
                if node.type == "aws_internet_gateway"
            ]
            group, rule = opened[0]
            ports = f"{rule.get('protocol', 'tcp')}/{rule.get('from_port')}"
            return (
                Hop("0.0.0.0/0", "the internet"),
                Hop(gateways[0].address, "an internet gateway on this VPC"),
                Hop(table.address, "routes 0.0.0.0/0 at that gateway"),
                Hop(subnet.address, "is associated with that route table"),
                Hop(group.address, f"admits the whole internet on {ports}"),
                Hop(interface.address, "is in that subnet and that group"),
            )
    return None
