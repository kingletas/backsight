"""The verdict line — the one strip that never leaves, and what it refuses to invent.

Section 1 of the UAT guide is accepted or rejected here. Both halves: the loud
one, where a thing is true and the line says so, and the quiet one, where
nothing is wrong and the line says **nothing at all**.
"""

from backsight.engine.presentation.status import Tone, build, plan_summary

FULL = {
    "counts": {"create": 2, "update": 1, "replace": 1},
    "planned": True,
    "cost": "$124/mo",
    "cost_direction": "↑",
    "exposures": 1,
    "coverage": 86,
    "tests": (4, 5),
}


# --- the verdict zone ------------------------------------------------------


def test_a_workspace_that_has_not_been_planned_says_so_and_says_how():
    """Blank is indistinguishable from broken."""
    said = [segment.text for segment in build().verdict]
    assert said == ["No plan yet", "Ctrl+Return to run one"]


def test_every_count_carries_a_glyph_because_a_bare_number_reads_as_a_total():
    assert plan_summary({"create": 2, "update": 1, "replace": 1}) == "＋2 ◆1 ▲1"


def test_an_action_with_no_count_is_left_out():
    assert plan_summary({"create": 2, "delete": 0}) == "＋2"


def test_an_empty_plan_says_nothing_rather_than_zeros():
    assert plan_summary({}) == ""


def test_each_count_is_a_segment_with_its_own_consequence():
    tones = {s.text: s.tone for s in build(planned=True, counts=FULL["counts"]).verdict}
    assert tones["＋2"] is Tone.SAFE
    assert tones["◆1"] is Tone.DISRUPTIVE
    assert tones["▲1"] is Tone.IRREVERSIBLE


def test_a_plan_that_matches_says_no_changes_once():
    said = [s.text for s in build(planned=True, counts={}).verdict]
    assert said == ["No changes", "Infrastructure matches the configuration"]
    assert "＋0" not in " ".join(said)


def test_a_stale_plan_marks_its_counts_as_of_when():
    """Counts from before an edit, presented as current, are the confident-but-
    wrong claim this product exists against."""
    line = build(planned=True, counts={"create": 2}, stale_edits=3)
    said = [s.text for s in line.verdict]
    assert said == ["＋2", "as of 3 edits ago"]
    assert line.verdict[-1].tone is Tone.DISRUPTIVE


def test_one_edit_is_singular():
    assert "as of 1 edit ago" in build(planned=True, counts={"create": 1}, stale_edits=1).texts()


def test_a_blocked_plan_turns_the_strip_and_names_how_many():
    line = build(blocked="Variable region is not set", problems=2)
    assert line.will_not_run
    assert line.verdict[0].text == "■ Will not run — 2 problems"
    assert line.verdict[0].tone is Tone.BLOCKING


def test_nothing_measured_before_the_error_is_shown_beside_it():
    """Last run's numbers next to a live failure are numbers presented as
    current that are not."""
    line = build(blocked="broken", problems=1, **FULL)
    assert line.chips == []


def test_an_apply_in_flight_says_where_it_is():
    assert build(applying=(2, 6)).verdict[0].text == "Applying · 2 of 6"


def test_an_apply_that_stopped_separates_what_changed_from_what_never_started():
    said = build(stopped=(3, 3)).verdict[0].text
    assert said == "Stopped · 3 applied, 3 untouched"


def test_a_run_in_flight_says_what_it_is_on():
    assert build(planning="prod-euw1").verdict[0].text == "Planning prod-euw1…"


# --- the chips -------------------------------------------------------------


def test_every_chip_opens_the_tab_that_explains_it():
    actions = {s.text: s.action for s in build(**FULL).chips}
    assert actions["$124/mo ↑"] == "cost"
    assert actions["1 exposure"] == "exposure"
    assert actions["86% converged"] == "convergence"
    assert actions["4/5 tests"] == "tests"


def test_the_counts_open_changes():
    assert all(s.action == "plan" for s in build(planned=True, counts={"create": 1}).verdict)


def test_one_exposure_is_singular():
    assert "1 exposure" in build(exposures=1).texts()
    assert "2 exposures" in build(exposures=2).texts()


def test_a_stale_upstream_stack_is_a_chip_and_says_how_many_are_waiting():
    said = build(stale_stacks=1, waiting_stacks=2).chips[0]
    assert said.text == "data is stale · 2 waiting"
    assert said.action == "stacks"


def test_a_buffer_that_disagrees_with_the_formatter_says_so_quietly():
    said = build(unformatted=True).chips[0]
    assert said.text == "unformatted"
    assert said.tone is Tone.FACT


def test_failing_tests_are_disruptive_and_passing_ones_are_a_fact():
    assert build(tests=(4, 5)).chips[0].tone is Tone.DISRUPTIVE
    assert build(tests=(5, 5)).chips[0].tone is Tone.FACT


# --- the quiet pass --------------------------------------------------------


def test_nothing_known_produces_no_chips_at_all():
    """An absence that looks like a measurement is the failure to avoid."""
    assert build().chips == []


def test_a_workspace_with_no_prices_gets_no_cost_chip():
    """Not a chip announcing that prices are not configured. A signal that
    fires when nothing is wrong trains people to stop reading the channel."""
    assert [s.action for s in build(**{**FULL, "cost": ""}).chips] == [
        "exposure",
        "convergence",
        "tests",
    ]


def test_a_workspace_where_every_stack_is_clean_gets_no_stacks_chip():
    assert [s.action for s in build(stale_stacks=0, waiting_stacks=0).chips] == []


def test_a_file_that_matches_the_formatter_says_nothing():
    assert [s.action for s in build(unformatted=False).chips] == []


def test_a_missing_measurement_is_absent_rather_than_zero():
    line = build(planned=True, counts={"create": 1})
    assert "0% converged" not in line.texts()
    assert "0 exposures" not in line.texts()


def test_coverage_of_zero_is_still_a_measurement_and_is_shown():
    """Nought per cent converged is a fact; not having run is not."""
    assert "0% converged" in build(coverage=0).texts()


# --- narrowing -------------------------------------------------------------


def test_chips_fall_off_the_right_cheapest_first():
    line = build(**FULL)
    assert [s.action for s in line.within(2).chips] == ["cost", "exposure"]
    assert [s.action for s in line.within(1).chips] == ["exposure"]


def test_the_verdict_never_drops_however_narrow_it_gets():
    line = build(**FULL)
    assert [s.text for s in line.within(0).verdict] == ["＋2", "◆1", "▲1"]
    assert line.within(0).chips == []


def test_narrowing_keeps_the_chips_in_the_order_they_are_read_in():
    line = build(**FULL)
    assert [s.action for s in line.within(3).chips] == ["cost", "exposure", "convergence"]


# --- file facts ------------------------------------------------------------


def test_the_file_facts_are_facts_and_the_branch_is_one_of_them():
    line = build(
        line=12, column=31, indentation="Spaces: 2", language="HCL", branch="add-db-access"
    )
    assert [s.text for s in line.facts] == [
        "Ln 12, Col 31",
        "Spaces: 2",
        "HCL",
        "⑂ add-db-access",
    ]


def test_the_line_carries_the_provider_when_it_is_known():
    assert "aws 5.82.0" in build(provider="aws 5.82.0").texts()


def test_only_the_thing_blocking_the_next_action_is_coloured_among_the_facts():
    line = build(line=1, column=1, language="HCL", provider="aws 5.82.0")
    assert all(s.tone is Tone.FACT for s in line.facts)
