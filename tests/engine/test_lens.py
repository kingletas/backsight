"""Sheet 11's code lens: three facts, and never a guessed one."""

from __future__ import annotations

import json
from pathlib import Path

from backsight.engine.insight.lens import SEPARATOR, UNTOUCHED, Lens, for_plan
from backsight.engine.insight.source_map import Location, SourceMap

ROOT = Path(__file__).resolve().parents[2]


def document(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / "plan" / f"{name}.json").read_text())


def mapped(*addresses: str) -> SourceMap:
    return SourceMap(
        places={
            address: Location(path=Path("main.tf"), line=index * 5 + 1, column=1)
            for index, address in enumerate(addresses)
        }
    )


def texts(lenses: list[Lens]) -> list[str]:
    return [lens.text for lens in lenses]


def test_a_replacement_reads_as_one_thing_not_two():
    """The plan says create and delete; a reader sees one replacement."""
    addresses = [c["address"] for c in document("replace")["resource_changes"]]
    lenses = for_plan(document("replace"), mapped(*addresses))
    assert any("replaced in plan" in text for text in texts(lenses))


def test_an_addition_says_added():
    addresses = [c["address"] for c in document("create")["resource_changes"]]
    lenses = for_plan(document("create"), mapped(*addresses))
    assert all("added in plan" in text for text in texts(lenses))


def test_a_destruction_says_destroyed():
    addresses = [c["address"] for c in document("destroy")["resource_changes"]]
    lenses = for_plan(document("destroy"), mapped(*addresses))
    assert any("destroyed in plan" in text for text in texts(lenses))


def test_a_resource_the_plan_does_not_touch_says_so():
    """Silence would read as "no plan has run", which is a different fact."""
    lenses = for_plan(document("create"), mapped("aws_instance.untouched"))
    assert texts(lenses) == [f"no references{SEPARATOR}{UNTOUCHED}"]


def test_a_resource_the_map_cannot_place_gets_no_lens():
    """A lens on line 0 is worse than no lens."""
    assert for_plan(document("create"), SourceMap(places={})) == []


def test_lenses_come_back_in_file_order():
    addresses = [c["address"] for c in document("create")["resource_changes"]]
    lenses = for_plan(document("create"), mapped(*addresses))
    assert [lens.line for lens in lenses] == sorted(lens.line for lens in lenses)


def test_one_reference_is_not_called_references():
    assert Lens(line=1, address="a", references=1, action="x").text.startswith("1 reference ")


def test_no_references_is_stated_rather_than_left_blank():
    assert Lens(line=1, address="a", references=0, action="x").text.startswith("no references")


def test_the_lens_never_mentions_money():
    """There is no pricing data, and $0/mo about an instance would be a lie."""
    for name in ("create", "replace", "destroy", "update"):
        addresses = [c["address"] for c in document(name)["resource_changes"]]
        for text in texts(for_plan(document(name), mapped(*addresses))):
            assert "$" not in text


def test_a_lens_can_leave_the_action_to_the_verdict():
    """Where both land on one line, "Add" and "added in plan" are one sentence."""
    lens = Lens(line=4, address="a", references=2, action="added in plan")
    assert lens.text == f"2 references{SEPARATOR}added in plan"
    assert lens.without_action == "2 references"
