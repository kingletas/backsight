"""Closing and sorting tabs never loses an edit nobody saved."""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.editor import Editor  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "stacks" / "plain" / "infra"
FILES = [ROOT / name / "main.tf" for name in ("network", "data", "api", "edge")]


def opened(editor: Editor) -> list[str]:
    return [page.path.parent.name for page, _tab in editor._each()]


def filled() -> Editor:
    editor = Editor()
    for path in FILES:
        editor.open(path)
    return editor


def test_sorting_by_name_puts_them_in_order():
    editor = filled()
    editor.sort_tabs("path")
    assert opened(editor) == ["api", "data", "edge", "network"]


def test_manual_is_the_absence_of_a_sort_not_a_sort():
    """It must leave them exactly where they are."""
    editor = filled()
    before = opened(editor)
    editor.sort_tabs("manual")
    assert opened(editor) == before


def test_sorting_by_recency_puts_the_last_looked_at_first():
    editor = filled()
    editor.open(FILES[0])
    editor.sort_tabs("recent")
    assert opened(editor)[0] == "network"


def test_an_unknown_sort_leaves_the_tabs_alone():
    editor = filled()
    before = opened(editor)
    editor.sort_tabs("by-the-phase-of-the-moon")
    assert opened(editor) == before


def test_closing_untouched_keeps_what_the_plan_touches():
    editor = filled()
    editor.close_untouched({FILES[0], FILES[2]})
    assert sorted(opened(editor)) == ["api", "network"]


def test_closing_untouched_never_closes_an_unsaved_edit():
    """Closing an edit nobody saved is not a tidy-up."""
    editor = filled()
    page = editor.pages[FILES[1].resolve()]
    page.buffer.insert_at_cursor("\n# edited\n")
    editor.close_untouched({FILES[0]})
    assert "data" in opened(editor)


def test_closing_files_gone_from_disk_leaves_the_ones_that_exist():
    editor = filled()
    editor.close_gone()
    assert len(opened(editor)) == 4


def test_a_file_deleted_under_us_is_closed(tmp_path: Path):
    editor = Editor()
    path = tmp_path / "main.tf"
    path.write_text('resource "terraform_data" "a" {}\n')
    editor.open(path)
    path.unlink()
    editor.close_gone()
    assert opened(editor) == []


def test_an_unsaved_edit_survives_its_file_being_deleted(tmp_path: Path):
    """The buffer is the only copy left; closing it is data loss."""
    editor = Editor()
    path = tmp_path / "main.tf"
    path.write_text("original\n")
    editor.open(path)
    editor.pages[path.resolve()].buffer.insert_at_cursor("edited\n")
    path.unlink()
    editor.close_gone()
    assert len(opened(editor)) == 1


def test_pinning_reports_which_state_it_is_now_in():
    editor = filled()
    assert editor.pin_current() is True
    assert editor.pin_current() is False


def test_pinning_with_nothing_open_is_not_an_error():
    assert Editor().pin_current() is False


def test_a_closed_tab_can_be_reopened():
    """A mis-click should cost one keystroke, not a hunt through the rail."""
    editor = filled()
    closed = editor.pages[FILES[3].resolve()].path
    editor.open(FILES[3])
    editor.close_current()
    assert editor.reopen_last_closed() == closed


def test_reopening_with_nothing_closed_finds_nothing():
    assert filled().reopen_last_closed() is None


def test_reopening_skips_a_file_that_is_open_again():
    """Otherwise it hands back a tab already in front of you."""
    editor = filled()
    editor.open(FILES[0])
    editor.close_current()
    editor.open(FILES[0])
    assert editor.reopen_last_closed() is None
