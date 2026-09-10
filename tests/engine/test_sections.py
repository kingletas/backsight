"""The panel must not contradict its own headline."""

from __future__ import annotations

from backsight.engine.insight.sections import (
    ACCESS_WAITING,
    COST_WAITING,
    Capabilities,
    State,
    describe,
)

PLAN = object()


def details(sections) -> dict[str, str]:
    return {section.title: section.detail for section in sections}


def states(sections) -> dict[str, State]:
    return {section.title: section.state for section in sections}


def test_with_no_plan_each_section_says_what_would_fill_it():
    """An empty state is an invitation, not a status report.

    "Needs a plan" says somebody failed to do something. These say what goes
    here, why it is empty, and the one action that fills it.
    """
    shown = describe(None, Capabilities())
    assert details(shown)["Monthly cost"] == COST_WAITING
    assert details(shown)["Exposure"] == ACCESS_WAITING


def test_with_a_plan_nothing_still_asks_for_a_plan():
    """ "2 to add" above "Needs a plan" is what this exists to stop."""
    shown = describe(PLAN, Capabilities())
    assert not any(said.startswith("Run a plan") for said in details(shown).values())


def test_cost_says_why_it_in_particular_is_empty():
    """No prices imported, which is a different thing from no cost. Nothing
    ships with prices in it — an invented one is a confident number about
    somebody's money."""
    shown = describe(PLAN, Capabilities())
    assert details(shown)["Monthly cost"] == "No prices imported yet, so nothing can be estimated"


def test_an_answer_replaces_the_caption_once_there_is_one():
    """The rail carried a sentence about there being no answer for as long as
    there was no engine behind it."""
    shown = describe(PLAN, Capabilities(cost_said="+12.50 USD a month"))
    assert details(shown)["Monthly cost"] == "+12.50 USD a month"

    scanned = describe(PLAN, Capabilities(policy_said="3 findings, 1 high"))
    assert details(scanned)["Policy checks"] == "3 findings, 1 high"


def test_exposure_names_the_thing_it_is_missing():
    shown = describe(PLAN, Capabilities())
    assert "access to the account" in details(shown)["Exposure"]


def test_policy_is_unconfigured_whether_or_not_a_plan_exists():
    """Nothing about a plan changes that no policy set is configured."""
    for plan in (None, PLAN):
        shown = describe(plan, Capabilities())
        assert "No policies configured" in details(shown)["Policy checks"]
        assert states(shown)["Policy checks"] is State.UNAVAILABLE


def test_a_configured_policy_with_no_plan_waits_for_the_plan():
    shown = describe(None, Capabilities(policy_set=True))
    assert details(shown)["Policy checks"].startswith("Run a plan")
    assert states(shown)["Policy checks"] is State.WAITING


def test_a_rehearsal_does_not_depend_on_a_plan():
    """It runs the real thing in a container; a plan is beside the point."""
    without = describe(None, Capabilities(container_runtime=True))
    with_plan = describe(PLAN, Capabilities(container_runtime=True))
    assert details(without)["Rehearsal"] == details(with_plan)["Rehearsal"]
    assert details(without)["Rehearsal"].startswith("Try this plan against a local copy")


def test_a_rehearsal_with_no_runtime_names_what_is_missing():
    shown = describe(PLAN, Capabilities())
    assert "Docker or Podman" in details(shown)["Rehearsal"]


def test_everything_available_leaves_every_section_ready():
    shown = describe(
        PLAN,
        Capabilities(
            policy_set=True,
            credentials=True,
            container_runtime=True,
            pricing_data=True,
            convergence_run=True,
        ),
    )
    assert all(not section.is_empty for section in shown)
    assert all(section.detail == "" for section in shown)


def test_waiting_and_unavailable_are_told_apart():
    """One is a thing to do next; the other is a thing to set up."""
    shown = describe(None, Capabilities())
    assert states(shown)["Monthly cost"] is State.WAITING
    assert states(shown)["Policy checks"] is State.UNAVAILABLE


def test_the_sections_keep_the_order_the_rail_puts_them_in():
    titles = [section.title for section in describe(None, Capabilities())]
    assert titles == ["Monthly cost", "Policy checks", "Exposure", "Rehearsal"]


def test_apply_says_it_needs_a_plan_before_there_is_one():
    from backsight.engine.insight.sections import NEEDS_PLAN, why_apply_is_blocked

    assert why_apply_is_blocked(None, Capabilities()) == NEEDS_PLAN


def a_plan_using(provider: str):
    """A plan shaped enough to be asked what it would reach."""
    from backsight.engine.plan.model import Action, Plan, ResourceChange

    return Plan(
        format_version="1.2",
        engine_version="1.12.6",
        changes=(
            ResourceChange(
                address="a.b",
                type="a",
                name="b",
                mode="managed",
                provider=provider,
                action=Action.CREATE,
            ),
        ),
    )


def test_apply_names_credentials_once_a_plan_reaches_a_real_provider():
    """The button and the status bar have to agree, or it reads as two bugs."""
    from backsight.engine.insight.sections import NEEDS_CREDENTIALS, why_apply_is_blocked

    plan = a_plan_using("registry.opentofu.org/hashicorp/aws")
    assert why_apply_is_blocked(plan, Capabilities()) == NEEDS_CREDENTIALS


def test_a_plan_that_reaches_nothing_outside_the_machine_needs_no_credentials():
    """`terraform_data` is the engine's own resource. Requiring keys for it
    meant the offline example workspace could never be applied, so the product
    could not show its own ending to anybody trying it."""
    from backsight.engine.insight.sections import why_apply_is_blocked

    assert why_apply_is_blocked(a_plan_using("terraform"), Capabilities()) is None
    # What a real plan document actually says — a list of plausible hosts
    # written from memory had three spellings and not this one.
    assert (
        why_apply_is_blocked(a_plan_using("terraform.io/builtin/terraform"), Capabilities()) is None
    )


def test_a_plan_mixing_the_two_still_needs_credentials():
    """One resource reaching an account is enough to need the keys for it."""
    from backsight.engine.insight.sections import NEEDS_CREDENTIALS, why_apply_is_blocked
    from backsight.engine.plan.model import Action, Plan, ResourceChange

    plan = Plan(
        format_version="1.2",
        engine_version="1.12.6",
        changes=(
            ResourceChange("a.b", "a", "b", "managed", "terraform", Action.CREATE),
            ResourceChange("c.d", "c", "d", "managed", "hashicorp/aws", Action.CREATE),
        ),
    )
    assert why_apply_is_blocked(plan, Capabilities()) == NEEDS_CREDENTIALS


def test_a_plan_that_changes_nothing_says_that_rather_than_asking_for_keys():
    from backsight.engine.insight.sections import NOTHING_TO_DO, why_apply_is_blocked

    assert why_apply_is_blocked(PLAN, Capabilities(credentials=True), changes=0) == NOTHING_TO_DO


def test_nothing_blocks_apply_when_everything_is_in_place():
    from backsight.engine.insight.sections import why_apply_is_blocked

    assert why_apply_is_blocked(PLAN, Capabilities(credentials=True), changes=2) is None


def test_the_rehearsal_never_claims_to_be_a_drift_check():
    """Two features were both called "Drift check". One runs the plan against a
    local emulator in a container and says nothing about whether reality has
    moved; the other is a refresh-only plan and needs no container at all."""
    from backsight.engine.insight.sections import REHEARSAL, describe

    for can in (Capabilities(), Capabilities(container_runtime=True)):
        for section in describe(PLAN, can):
            if section.title == REHEARSAL:
                assert "drift" not in section.detail.lower()
