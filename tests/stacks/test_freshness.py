"""A stack is stale when something it depends on has been applied since.

Both halves, and the quiet one first: on the ordinary day this says nothing,
which is the whole reason it replaced a resident rail section.
"""

from pathlib import Path

from backsight.engine.stacks.freshness import APPLIED, PLANNED, Event, stale
from backsight.engine.stacks.model import Definitions, Stack


def stacks(**edges: list[str]) -> Definitions:
    made = {
        name: Stack(name=name, path=name, needs={one: ("id",) for one in upstream})
        for name, upstream in edges.items()
    }
    return Definitions(stacks=made, path=Path("stacks.toml"))


def happened(kind: str, stack: str, at: str) -> Event:
    return Event(kind=kind, stack=stack, at=at)


def test_nothing_is_stale_when_nothing_has_been_applied():
    """The quiet case, and the one it will be in almost every day."""
    assert stale(stacks(api=["data"], data=[]), []) == []


def test_a_stack_planned_after_its_upstream_applied_is_not_stale():
    log = [
        happened(APPLIED, "data", "2026-09-09T10:00:00"),
        happened(PLANNED, "api", "2026-09-09T11:00:00"),
    ]
    assert stale(stacks(api=["data"], data=[]), log) == []


def test_a_stack_planned_before_its_upstream_applied_is_stale():
    log = [
        happened(PLANNED, "api", "2026-09-09T10:00:00"),
        happened(APPLIED, "data", "2026-09-09T11:00:00"),
    ]
    found = stale(stacks(api=["data"], data=[]), log)
    assert [one.stack for one in found] == ["api"]
    assert found[0].behind == ("data",)
    assert not found[0].never_planned


def test_a_stack_never_planned_at_all_is_waiting_rather_than_stale():
    """Different sentence, same consequence: it has not looked since the
    upstream moved."""
    log = [happened(APPLIED, "data", "2026-09-09T11:00:00")]
    found = stale(stacks(api=["data"], data=[]), log)
    assert found[0].never_planned
    assert "never been planned" in str(found[0])


def test_it_names_every_upstream_that_moved_newest_first():
    log = [
        happened(PLANNED, "api", "2026-09-09T09:00:00"),
        happened(APPLIED, "data", "2026-09-09T10:00:00"),
        happened(APPLIED, "network", "2026-09-09T11:00:00"),
    ]
    assert stale(stacks(api=["data", "network"], data=[], network=[]), log)[0].behind == (
        "network",
        "data",
    )


def test_an_upstream_that_has_never_been_applied_does_not_make_anything_stale():
    log = [happened(PLANNED, "api", "2026-09-09T09:00:00")]
    assert stale(stacks(api=["data"], data=[]), log) == []


def test_a_workspace_with_no_stack_file_is_never_stale():
    log = [happened(APPLIED, "data", "2026-09-09T11:00:00")]
    assert stale(Definitions(), log) == []


def test_an_entry_with_no_stack_name_is_about_a_module_nobody_grouped():
    log = [
        Event(kind=APPLIED, stack="", at="2026-09-09T11:00:00"),
        happened(PLANNED, "api", "2026-09-09T09:00:00"),
    ]
    assert stale(stacks(api=["data"], data=[]), log) == []
