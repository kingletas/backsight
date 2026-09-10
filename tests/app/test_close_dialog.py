"""What the close question says, and when it is not asked at all."""

from pathlib import Path

from backsight.app.close_dialog import Answer, body, heading
from backsight.engine.layout.tabs import OpenTab, Scope, select


def strip():
    return [
        OpenTab(path=Path("modules/rds/main.tf"), unsaved=True, changed_lines=14),
        OpenTab(path=Path("modules/vpc/main.tf")),
        OpenTab(path=Path("outputs.tf")),
    ]


def test_the_heading_names_the_scope_and_the_count():
    chosen = select(strip(), 0, Scope.RIGHT)
    assert heading(chosen) == "Close 2 tabs to the right?"


def test_one_tab_is_asked_about_by_name():
    """ "Close 1 tab all?" was never English, and nothing ever called this."""
    chosen = select([strip()[0]], 0, Scope.ALL)
    assert heading(chosen) == "Close main.tf?"


def test_closing_one_of_several_still_names_the_file():
    chosen = select(strip(), 0, Scope.THIS)
    assert heading(chosen) == "Close main.tf?"


def test_the_body_names_the_file_and_the_damage():
    """Fourteen changed lines is a decision; "unsaved changes" is a shrug."""
    said = body(select(strip(), 1, Scope.ALL))
    assert "One has unsaved changes." in said
    assert "main.tf — 14 lines changed" in said


def test_several_unsaved_files_are_counted_and_listed():
    tabs = [
        OpenTab(path=Path("a.tf"), unsaved=True, changed_lines=2),
        OpenTab(path=Path("b.tf"), unsaved=True, changed_lines=7),
    ]
    said = body(select(tabs, 0, Scope.ALL))
    assert "2 have unsaved changes." in said
    assert "a.tf — 2 lines changed" in said
    assert "b.tf — 7 lines changed" in said


def test_nothing_unsaved_means_nothing_to_say():
    saved = [OpenTab(path=Path("a.tf")), OpenTab(path=Path("b.tf"))]
    assert body(select(saved, 0, Scope.ALL)) == ""


def test_every_answer_is_explicit():
    """No option quietly destroys work; each says what it does."""
    assert {answer.value for answer in Answer} == {"cancel", "keep-open", "discard", "save"}
