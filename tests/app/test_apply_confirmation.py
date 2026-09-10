"""The last screen before production changes.

The button label is the last warning anybody reads, so it names the destruction
rather than hiding it behind the word Apply.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backsight.engine.plan.apply import Target, confirmation_for, digest_of, may_apply
from backsight.engine.plan.model import read

ROOT = Path(__file__).resolve().parents[2]
PLANS = ROOT / "fixtures" / "plan"


@pytest.fixture
def artifact(tmp_path):
    path = tmp_path / "speculative.tfplan"
    path.write_bytes(b"a plan artifact")
    return path


def confirm(name, artifact, target=None):
    return confirmation_for(read(PLANS / f"{name}.json"), artifact, target)


def test_a_plan_that_destroys_nothing_says_apply(artifact):
    found = confirm("create", artifact)
    assert found.button_label == "Apply"
    assert found.is_destructive is False
    assert found.sentences()[0] == "Nothing will be destroyed."


def test_a_destroy_is_named_in_the_button(artifact):
    found = confirm("destroy", artifact)
    assert found.button_label == "Destroy 1 and apply"
    assert found.destroy_count == 1


def test_a_replacement_counts_as_a_destruction_in_the_button(artifact):
    """The object goes away and a new one arrives. The button says so."""
    found = confirm("replace", artifact)
    assert found.button_label == "Destroy 1 and apply"
    assert found.replaced == ("terraform_data.api",)
    assert "destroyed and recreated" in " ".join(found.sentences())


def test_the_reason_for_a_replacement_is_named(artifact):
    found = confirm("replace", artifact)
    assert found.reasons() == ["terraform_data.api — replacement forced by triggers_replace"]


def test_several_destructions_are_counted_together(tmp_path, artifact):
    from backsight.engine.plan.model import parse

    plan = parse(
        {
            "format_version": "1.2",
            "terraform_version": "1.12.6",
            "resource_changes": [
                {
                    "address": f"null_resource.n{n}",
                    "type": "null_resource",
                    "name": f"n{n}",
                    "mode": "managed",
                    "provider_name": "null",
                    "change": {"actions": actions},
                }
                for n, actions in enumerate([["delete"], ["delete"], ["delete", "create"]])
            ],
        }
    )
    found = confirmation_for(plan, artifact)
    assert found.button_label == "Destroy 3 and apply"


def test_an_unknown_account_is_said_rather_than_invented(artifact):
    found = confirm("create", artifact)
    assert found.target.is_known is False
    assert "not known" in " ".join(found.sentences())


def test_a_known_target_carries_its_own_details(artifact):
    target = Target(
        account="prod-euw1",
        region="eu-west-1",
        role="backsight-apply-network",
        identity="j.okafor",
        expires_at=datetime.now(UTC) + timedelta(minutes=41),
    )
    found = confirm("create", artifact, target)
    assert found.target.is_known
    assert found.target.minutes_left() in (40, 41)
    assert "not known" not in " ".join(found.sentences())


def test_an_expired_session_reports_no_time_left(artifact):
    target = Target(account="a", region="b", expires_at=datetime.now(UTC) - timedelta(minutes=5))
    assert confirm("create", artifact, target).target.minutes_left() == 0


def test_a_plan_that_has_not_changed_may_be_applied(artifact):
    allowed, why = may_apply(confirm("create", artifact))
    assert allowed and why == ""


def test_a_plan_that_changed_since_review_may_not_be_applied(artifact):
    """FR-ST-03. Re-planning here would apply something nobody reviewed."""
    found = confirm("create", artifact)
    artifact.write_bytes(b"a different plan artifact")
    allowed, why = may_apply(found)
    assert allowed is False
    assert "changed after it was reviewed" in why


def test_a_plan_whose_artifact_is_gone_may_not_be_applied(artifact):
    found = confirm("create", artifact)
    artifact.unlink()
    allowed, why = may_apply(found)
    assert allowed is False
    assert "is gone" in why


def test_a_plan_that_errored_may_not_be_applied(artifact):
    from backsight.engine.plan.model import Plan

    found = confirmation_for(
        Plan(format_version="1.2", engine_version="1.12.6", errored=True), artifact
    )
    allowed, why = may_apply(found)
    assert allowed is False
    assert "reported errors" in why


def test_the_digest_is_of_the_artifact_and_not_of_the_json(artifact):
    first = digest_of(artifact)
    artifact.write_bytes(b"a plan artifact ")
    assert digest_of(artifact) != first
