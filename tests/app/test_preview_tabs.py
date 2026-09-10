"""One reused tab while browsing, and a new one only when it is asked for."""

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


def test_browsing_reuses_one_tab_rather_than_leaving_a_row_of_them():
    """Twenty clicks through a repository should not leave twenty tabs."""
    editor = Editor()
    for path in FILES:
        editor.open(path, preview=True)
    assert len(opened(editor)) == 1
    assert opened(editor) == ["edge"]


def test_opening_without_preview_keeps_every_tab():
    editor = Editor()
    for path in FILES:
        editor.open(path)
    assert len(opened(editor)) == 4


def test_editing_a_preview_keeps_it_open():
    """The moment somebody types they are no longer browsing."""
    editor = Editor()
    editor.open(FILES[0], preview=True)
    editor.pages[FILES[0].resolve()].buffer.insert_at_cursor("\n# edited\n")
    assert editor.preview is None
    editor.open(FILES[1], preview=True)
    assert sorted(opened(editor)) == ["data", "network"]


def test_a_tab_that_vanished_under_an_edit_would_be_the_worst_surprise():
    """The same thing said as a behaviour: an edited file is never replaced."""
    editor = Editor()
    editor.open(FILES[0], preview=True)
    editor.pages[FILES[0].resolve()].buffer.insert_at_cursor("x")
    for path in FILES[1:]:
        editor.open(path, preview=True)
    assert "network" in opened(editor)


def test_promoting_by_hand_is_what_a_double_click_does():
    editor = Editor()
    editor.open(FILES[0], preview=True)
    editor.promote(FILES[0])
    assert editor.preview is None
    editor.open(FILES[1], preview=True)
    assert sorted(opened(editor)) == ["data", "network"]


def test_a_file_already_open_is_focused_rather_than_previewed():
    """It was opened deliberately; a preview would demote it."""
    editor = Editor()
    editor.open(FILES[0])
    editor.open(FILES[1], preview=True)
    editor.open(FILES[0], preview=True)
    assert editor.preview == FILES[1].resolve()
    assert sorted(opened(editor)) == ["data", "network"]


def test_closing_the_preview_leaves_nothing_pointing_at_it():
    editor = Editor()
    editor.open(FILES[0], preview=True)
    editor.close_current()
    assert editor.preview is None


def test_the_preview_carries_a_mark_of_its_own():
    """`Adw.TabPage` has no italic and no markup, so an icon stands in."""
    editor = Editor()
    page = editor.open(FILES[0], preview=True)
    tab = editor._page_for(page)
    assert tab.get_icon() is not None
    assert "Preview" in tab.get_tooltip()


def test_promoting_takes_the_mark_away():
    editor = Editor()
    page = editor.open(FILES[0], preview=True)
    editor.promote(FILES[0])
    tab = editor._page_for(page)
    assert tab.get_icon() is None
    assert "Preview" not in tab.get_tooltip()


def test_promoting_something_that_is_not_the_preview_does_nothing():
    editor = Editor()
    editor.open(FILES[0], preview=True)
    editor.promote(FILES[1])
    assert editor.preview == FILES[0].resolve()
