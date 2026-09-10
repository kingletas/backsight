"""What changed outside Terraform, read from real refresh-only runs.

Drift needs a resource with something behind it — `terraform_data` keeps no
reality outside its own state, so a refresh of it can never disagree. These
captures use the `local` provider, whose resources are files: one edited by
hand, one deleted.
"""

from __future__ import annotations

import json
from pathlib import Path

from backsight.engine.plan.drifting import (
    Drift,
    Drifted,
    drift_events,
    from_document,
    from_stream,
)

FIXTURES = Path(__file__).resolve().parents[1].parent / "fixtures" / "drift"


def lines(name: str) -> list[str]:
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


def document() -> dict:
    return json.loads((FIXTURES / "refresh-only-plan.json").read_text(encoding="utf-8"))


def test_it_finds_what_moved_in_a_real_run():
    found = from_stream(lines("detected.jsonl"))
    assert found.count == 2
    assert {resource.address for resource in found.resources} == {
        "local_file.config",
        "local_file.notes",
    }


def test_a_clean_workspace_says_nothing_has_changed():
    """A check that has only ever been seen firing has not been tested."""
    found = from_stream(lines("none.jsonl"))
    assert found.checked
    assert found.is_clean
    assert found.count == 0
    assert found.headline == "Nothing has changed outside Terraform"


def test_the_headline_counts_what_is_gone_separately():
    found = from_stream(lines("detected.jsonl"))
    assert "2 resources changed outside Terraform" in found.headline
    assert "2 of them no longer there" in found.headline


def test_the_document_says_which_attributes_moved():
    """The events carry the addresses; the plan document carries the values,
    and the attribute name is what lets somebody judge in a second."""
    found = from_document(document())
    by_address = {resource.address: resource for resource in found.resources}
    config = by_address["local_file.config"]
    assert config.differences
    assert any(difference.name == "content" for difference in config.differences)


def test_computed_hashes_are_not_reported_as_drift():
    """Every provider computes them and nobody edited them. Six lines that
    never mean anything would bury the one that does."""
    found = from_document(document())
    named = {difference.name for resource in found.resources for difference in resource.differences}
    assert not named & {"id", "content_md5", "content_sha256", "content_base64sha256"}


def test_a_difference_reads_as_a_before_and_an_after():
    said = str(
        Drifted(
            address="local_file.config",
            action="update",
            differences=(
                __import__("backsight.engine.plan.drifting", fromlist=["Difference"]).Difference(
                    name="content", was="mode = production\n", now="edited\n"
                ),
            ),
        ).differences[0]
    )
    assert "content:" in said
    assert "→" in said
    assert "⏎" in said, "a newline in a value must not break the line it is shown on"


def test_a_long_value_is_cut_rather_than_wrapping_the_panel():
    from backsight.engine.plan.drifting import Difference

    said = str(Difference(name="content", was="x" * 200, now="y"))
    assert len(said) < 100
    assert "…" in said


def test_a_resource_that_is_gone_says_so_in_those_words():
    found = from_stream(lines("detected.jsonl"))
    assert all(resource.is_gone for resource in found.resources)
    assert found.resources[0].summary == "no longer there as Terraform recorded it"


def test_gone_never_claims_more_than_the_engine_said():
    """The `local` provider reports an edited file this way. Saying "no longer
    exists" of a file sitting on disk would invent a meaning the engine did not
    give."""
    found = from_stream(lines("detected.jsonl"))
    for resource in found.resources:
        assert "does not exist" not in resource.summary
        assert "deleted" not in resource.summary


def test_nothing_checked_yet_invites_rather_than_reporting():
    assert "Run a drift check" in Drift().headline


def test_a_failure_is_said_rather_than_shown_as_no_drift():
    """Reporting a check that could not run as "nothing has changed" is the
    worst answer a checker can give."""
    found = Drift(failure="No valid credential sources found")
    assert not found.is_clean
    assert found.headline == "No valid credential sources found"


def test_only_drift_events_are_read_from_the_stream():
    assert len(drift_events(lines("detected.jsonl"))) == 2
    assert drift_events(["not json", '{"type":"refresh_start"}']) == []
