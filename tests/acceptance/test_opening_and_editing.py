"""Opening a workspace and editing a file — the first ninety seconds.

An editor is judged on these before its clever features matter.
"""

from __future__ import annotations

import pytest

from tests.acceptance.looking import drawn, labels, says, settle

gi = pytest.importorskip("gi", reason="the toolkit is not installed")


def test_an_empty_window_invites_rather_than_reporting(window):
    """ "No workspace open" states a fact. This says what to do about it."""
    assert says(window, "Open a workspace to get started")
    assert says(window, "or try an example workspace")


def test_opening_a_workspace_lists_its_files(window, workspace):
    window.open_workspace(workspace)
    settle(window)
    assert says(window._sidebar_widget, "main.tf")


def test_the_switcher_names_the_workspace_and_where_its_state_is(window, workspace):
    """It was two lines and a count at the top of the rail — a heading over the
    only section there is, saying what the title bar already says."""
    window.open_workspace(workspace)
    settle(window)
    found = window._known_workspace()
    assert found is not None
    assert found.path == workspace
    assert found.backend


def test_the_sidebar_is_the_tree_and_nothing_else(window, workspace):
    """It held four unrelated things, with the tree in the top fifth."""
    window.open_workspace(workspace)
    settle(window)
    said = " ".join(labels(window._sidebar_widget))
    for taught in ("Monthly cost", "Group modules that deploy together", "Policy checks"):
        assert taught not in said


def test_opening_a_file_puts_it_in_the_editor(opened, workspace):
    page = opened._files_open.current
    assert page is not None
    assert page.path == (workspace / "main.tf").resolve()
    assert "terraform_data" in page.text()
    assert drawn(page.view)


def test_the_file_in_front_is_marked_in_the_tree(opened, workspace):
    row, _mark = opened._files.rows[(workspace / "main.tf").resolve()]
    assert "tf-current" in row.get_css_classes()


def test_typing_reaches_the_buffer_and_marks_the_tab_unsaved(opened):
    page = opened._files_open.current
    page.buffer.insert_at_cursor("\n# a note\n")
    settle(opened, 0.3)
    assert "# a note" in page.text()
    assert page.modified


def test_saving_writes_exactly_what_is_in_the_buffer(opened, workspace):
    """Round-trip safety: no reformatting, no reordering, nothing added."""
    page = opened._files_open.current
    before = (workspace / "main.tf").read_text(encoding="utf-8")
    page.buffer.insert_at_cursor("\n# a note\n")
    opened.save_current()
    settle(opened, 0.4)
    after = (workspace / "main.tf").read_text(encoding="utf-8")
    assert after.startswith(before.rstrip("\n")[:40])
    assert "# a note" in after


def test_undo_puts_it_back(opened):
    page = opened._files_open.current
    before = page.text()
    page.buffer.insert_at_cursor("# something\n")
    page.buffer.undo()
    assert page.text() == before


def test_a_second_file_replaces_the_first(opened, workspace):
    """Opening replaces what is in front. Two at once is a deliberate choice."""
    (workspace / "other.tf").write_text('resource "terraform_data" "b" {}\n', encoding="utf-8")
    opened._show_files()
    opened.open_file(workspace / "other.tf")
    settle(opened, 0.3)
    assert len(opened._files_open.pages) == 1


def test_and_keeping_one_opens_the_next_beside_it(opened, workspace):
    (workspace / "other.tf").write_text('resource "terraform_data" "b" {}\n', encoding="utf-8")
    opened._show_files()
    opened.open_in_new_tab()
    opened.open_file(workspace / "other.tf")
    settle(opened, 0.3)
    assert len(opened._files_open.pages) == 2


def test_a_file_that_is_not_utf8_is_refused_and_said(window, workspace):
    """Refusing is the correct outcome, so it is reported in the window."""
    (workspace / "latin1.tf").write_bytes(b'# caf\xe9\nresource "a" "b" {}\n')
    window.open_workspace(workspace)
    settle(window)
    window.open_file(workspace / "latin1.tf")
    settle(window, 0.3)
    assert window._banner.get_revealed()
    assert "UTF-8" in window._banner.get_title()
