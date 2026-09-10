"""Scope and filter are two axes, and the cost is named once."""

from pathlib import Path

import pytest

from backsight.engine.layout.tabs import (
    Filter,
    OpenTab,
    Scope,
    SortOrder,
    changed_lines,
    damage,
    select,
    sort_tabs,
)


def tab(name: str, **kwargs) -> OpenTab:
    return OpenTab(path=Path(f"modules/{name}"), **kwargs)


STRIP = [
    tab("a.tf"),
    tab("b.tf", unsaved=True, changed_lines=14),
    tab("c.tf"),  # active
    tab("d.tf", on_disk=False),
    tab("e.tf", unsaved=True, changed_lines=1, touched_by_plan=True),
]
ACTIVE = 2


# --- scope ----------------------------------------------------------------


def test_close_others_takes_everything_but_the_active_one():
    chosen = select(STRIP, ACTIVE, Scope.OTHERS)
    assert chosen.count == 4
    assert all(t.path.name != "c.tf" for t in chosen.tabs)


def test_close_to_the_left_and_right_split_at_the_active_tab():
    assert [t.path.name for t in select(STRIP, ACTIVE, Scope.LEFT).tabs] == ["a.tf", "b.tf"]
    assert [t.path.name for t in select(STRIP, ACTIVE, Scope.RIGHT).tabs] == ["d.tf", "e.tf"]


def test_close_all_takes_the_active_one_too():
    assert select(STRIP, ACTIVE, Scope.ALL).count == 5


def test_a_pinned_tab_is_never_taken():
    strip = [*STRIP, tab("pinned.tf", pinned=True)]
    assert all(t.path.name != "pinned.tf" for t in select(strip, ACTIVE, Scope.ALL).tabs)


# --- filter ---------------------------------------------------------------


def test_saved_only_is_the_scope_times_filter_product_collapsed():
    """The reference menu spells this out as its own item for every scope."""
    chosen = select(STRIP, ACTIVE, Scope.ALL, Filter.SAVED_ONLY)
    assert [t.path.name for t in chosen.tabs] == ["a.tf", "c.tf", "d.tf"]
    assert chosen.costs_work is False


def test_files_gone_from_disk_earns_its_place_after_a_branch_switch():
    chosen = select(STRIP, ACTIVE, Scope.ALL, Filter.GONE_FROM_DISK)
    assert [t.path.name for t in chosen.tabs] == ["d.tf"]


def test_not_touched_by_the_plan_is_close_unmodified_for_infrastructure():
    chosen = select(STRIP, ACTIVE, Scope.ALL, Filter.NOT_IN_PLAN)
    assert "e.tf" not in [t.path.name for t in chosen.tabs]


def test_a_filter_combines_with_any_scope():
    chosen = select(STRIP, ACTIVE, Scope.RIGHT, Filter.SAVED_ONLY)
    assert [t.path.name for t in chosen.tabs] == ["d.tf"]


# --- the cost, named before anything is clicked ---------------------------


def test_the_menu_item_carries_the_count_and_the_unsaved_count():
    """`Close others · 2 unsaved` means the dialog is rarely a surprise."""
    assert select(STRIP, ACTIVE, Scope.OTHERS).label() == "4 · 2 unsaved"


def test_a_selection_with_nothing_unsaved_says_only_its_count():
    assert select(STRIP, ACTIVE, Scope.ALL, Filter.SAVED_ONLY).label() == "3"


def test_an_empty_selection_says_so():
    assert select([], 0, Scope.ALL).label() == "none"


def test_no_dialog_at_all_when_nothing_is_unsaved():
    """Confirming a harmless action teaches people to click through confirmations."""
    assert select(STRIP, ACTIVE, Scope.ALL, Filter.SAVED_ONLY).costs_work is False
    assert select(STRIP, ACTIVE, Scope.ALL).costs_work is True


def test_the_damage_names_the_file_and_how_much():
    """Fourteen changed lines is a decision; "unsaved changes" is a shrug."""
    said = damage(select(STRIP, ACTIVE, Scope.ALL))
    assert "b.tf — 14 lines changed" in said
    assert "e.tf — 1 line changed" in said


def test_an_unsaved_file_with_no_line_count_still_says_something():
    selection = select([tab("x.tf", unsaved=True)], 0, Scope.ALL)
    assert damage(selection) == ["x.tf — unsaved"]


# --- counting the damage --------------------------------------------------


def test_changed_lines_counts_only_what_differs():
    assert changed_lines("a\nb\nc\n", "a\nB\nc\n") == 1
    assert changed_lines("a\nb\nc\n", "a\nb\nc\n") == 0


def test_changed_lines_counts_additions_and_removals():
    assert changed_lines("a\nc\n", "a\nb\nc\n") == 1
    assert changed_lines("a\nb\nc\n", "a\nc\n") == 1


# --- sorting --------------------------------------------------------------


def test_manual_leaves_the_strip_exactly_as_it_is():
    assert sort_tabs(STRIP, SortOrder.MANUAL) == STRIP


def test_sorting_by_name_ignores_the_path():
    strip = [tab("z/a.tf"), tab("a/z.tf")]
    assert [t.path.name for t in sort_tabs(strip, SortOrder.NAME)] == ["a.tf", "z.tf"]


def test_sorting_by_plan_impact_puts_the_busiest_files_first():
    """Only possible because the plan is already in memory."""
    strip = [tab("a.tf", plan_changes=1), tab("b.tf", plan_changes=9), tab("c.tf")]
    assert [t.path.name for t in sort_tabs(strip, SortOrder.PLAN_IMPACT)] == [
        "b.tf",
        "a.tf",
        "c.tf",
    ]


def test_sorting_by_recent_use_puts_the_newest_first():
    strip = [tab("a.tf", used_at=1.0), tab("b.tf", used_at=3.0), tab("c.tf", used_at=2.0)]
    assert [t.path.name for t in sort_tabs(strip, SortOrder.RECENT)] == ["b.tf", "c.tf", "a.tf"]


@pytest.mark.parametrize("order", list(SortOrder))
def test_no_sort_ever_loses_or_invents_a_tab(order):
    assert sorted(t.path for t in sort_tabs(STRIP, order)) == sorted(t.path for t in STRIP)
