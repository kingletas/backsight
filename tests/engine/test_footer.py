"""The footer offers what to do next, and Apply only when apply is possible."""

from __future__ import annotations

from dataclasses import dataclass

from backsight.engine.plan.footer import Situation, footer


@dataclass(frozen=True)
class Complaint:
    path: str = ""


PLAN = object()


def test_before_anything_it_offers_to_plan():
    assert footer(Situation()).action == "Run plan"


def test_while_planning_the_action_is_to_stop():
    said = footer(Situation(running=True, elapsed=12.4))
    assert said.action == "Cancel"
    assert said.detail == "Planning… 12s"


def test_a_failed_plan_offers_the_fix_when_there_is_one():
    said = footer(Situation(errors=[Complaint("main.tf")], fixable=True))
    assert said.action == "Fix and re-plan"


def test_and_offers_to_try_again_when_there_is_not():
    said = footer(Situation(errors=[Complaint("main.tf")]))
    assert said.action == "Re-plan"


def test_the_supporting_text_names_the_file():
    said = footer(Situation(errors=[Complaint("main.tf"), Complaint("main.tf")]))
    assert said.detail == "2 errors in main.tf"


def test_and_counts_the_files_when_there_are_several():
    said = footer(Situation(errors=[Complaint("main.tf"), Complaint("vars.tf")]))
    assert said.detail == "2 errors in 2 files"


def test_a_count_with_nowhere_to_point_is_still_a_count():
    assert footer(Situation(errors=[Complaint()])).detail == "1 error"


def test_apply_is_absent_everywhere_it_could_not_work():
    """Not disabled — absent. A dead primary action makes the footer scenery."""
    for now in (
        Situation(),
        Situation(running=True),
        Situation(errors=[Complaint("main.tf")]),
        Situation(plan=PLAN, changes=3, policy="no-public-db"),
        Situation(plan=PLAN, changes=3, warnings=[Complaint()]),
    ):
        said = footer(now)
        assert said is None or said.command != "apply", now


def test_nothing_to_do_means_no_footer_at_all():
    assert footer(Situation(plan=PLAN, changes=0)) is None


def test_a_policy_failure_names_the_policy():
    said = footer(Situation(plan=PLAN, changes=3, policy="no-public-db"))
    assert said.detail == "no-public-db blocks apply"


def test_warnings_ask_to_be_read_before_applying():
    said = footer(Situation(plan=PLAN, changes=13, warnings=[Complaint(), Complaint()]))
    assert said.action == "Review 13 changes"
    assert said.detail == "2 warnings, none blocking"


def test_and_step_out_of_the_way_once_they_have_been():
    said = footer(Situation(plan=PLAN, changes=13, warnings=[Complaint()], reviewed=True))
    assert said.command == "apply"


def test_a_ready_plan_says_how_much_it_is_applying():
    said = footer(Situation(plan=PLAN, changes=13, irreversible=2))
    assert said.action == "Apply 13 changes"
    assert said.detail == "2 irreversible"


def test_one_change_is_not_one_changes():
    assert footer(Situation(plan=PLAN, changes=1)).action == "Apply 1 change"


def test_typing_is_asked_for_only_where_something_cannot_be_undone():
    assert not footer(Situation(plan=PLAN, changes=3, environment="prod")).wants_confirmation
    assert (
        footer(Situation(plan=PLAN, changes=3, irreversible=1, environment="prod")).confirm
        == "prod"
    )


def test_no_supporting_text_ever_asks_the_reader_to_go_and_find_the_blocker():
    for now in (
        Situation(),
        Situation(running=True),
        Situation(errors=[Complaint("main.tf")]),
        Situation(plan=PLAN, changes=3, policy="p"),
        Situation(plan=PLAN, changes=3, irreversible=1),
    ):
        said = footer(now)
        assert said is None or "blocking" not in said.detail or said.detail.startswith("p ")


def test_the_footer_names_local_state_at_the_moment_it_costs_something():
    """It was a banner across the top of the window on open, which is hours
    before it means anything and is exactly where it gets dismissed.

    The footer is the last thing read before Apply is pressed, so it is where
    what applying *costs* belongs."""
    found = footer(Situation(plan=object(), changes=3, local_state=True))
    assert found.command == "apply"
    assert "state is on this machine only" in found.detail


def test_it_says_nothing_about_state_when_the_state_is_shared():
    found = footer(Situation(plan=object(), changes=3, local_state=False))
    assert "machine" not in found.detail


def test_it_says_both_when_both_are_true():
    found = footer(Situation(plan=object(), changes=3, irreversible=1, local_state=True))
    assert found.detail == "1 irreversible · state is on this machine only"


# --- how old the plan is ---------------------------------------------------


def test_a_fresh_plan_says_nothing_about_its_age():
    """Saying "planned 2 seconds ago" on every apply is a line nobody reads."""
    said = footer(Situation(plan=object(), changes=2, plan_age=5.0))
    assert "planned" not in said.detail


def test_a_plan_that_has_been_sitting_says_when_it_was_taken():
    """Infrastructure moves. The last thing read before an irreversible press
    should say which moment the plan describes."""
    said = footer(Situation(plan=object(), changes=2, plan_age=15 * 60))
    assert "planned 15 minutes ago" in said.detail


def test_an_old_plan_is_counted_in_hours():
    said = footer(Situation(plan=object(), changes=2, plan_age=3 * 3600))
    assert "planned 3 hours ago" in said.detail


def test_the_age_sits_beside_the_other_facts_rather_than_replacing_them():
    said = footer(
        Situation(plan=object(), changes=2, irreversible=1, plan_age=15 * 60, local_state=True)
    )
    assert "1 irreversible" in said.detail
    assert "planned 15 minutes ago" in said.detail
    assert "state is on this machine only" in said.detail
