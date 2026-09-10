"""The find row says how many it found, and how many it will change."""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")

from gi.repository import GLib, GtkSource  # noqa: E402

from backsight.app.find import Search  # noqa: E402
from backsight.app.find_bar import NOTHING, FindBar, summary  # noqa: E402
from backsight.app.window import Window  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "fixtures" / "workspace"


def settle(seconds: float = 2.0) -> None:
    """Runs the main loop until the background scan has reported.

    `GtkSource.SearchContext` counts asynchronously: the count is -1 and the
    notify arrives later, so a synchronous read always sees "still counting".
    """
    context = GLib.MainContext.default()
    deadline = GLib.get_monotonic_time() + int(seconds * 1_000_000)
    while GLib.get_monotonic_time() < deadline:
        if not context.pending():
            break
        context.iteration(False)


def searching(text: str) -> Search:
    buffer = GtkSource.Buffer()
    buffer.set_text(text)
    return Search(buffer)


def test_a_scan_still_running_is_not_reported_as_zero():
    """`-1` means counting. Printing "no matches" then would be a lie."""
    assert summary(-1) != NOTHING
    assert summary(0) == NOTHING


def test_one_match_is_not_called_matches():
    assert summary(1) == "1 match"
    assert summary(3) == "3 matches"


def test_typing_reports_how_many_were_found():
    bar = FindBar()
    bar.search_in(searching("api api api\nworker\n"))
    bar.term.set_text("api")
    settle()
    assert "3" in bar.count


def test_an_empty_term_says_nothing_rather_than_no_matches():
    """Before anyone has typed, "no matches" is not a fact about anything."""
    bar = FindBar()
    bar.search_in(searching("api\n"))
    bar.term.set_text("")
    assert bar.count == ""


def test_replace_all_is_dead_until_there_is_something_to_replace():
    bar = FindBar()
    bar.search_in(searching("api\n"))
    bar.term.set_text("nothing_here")
    settle()
    assert not bar._replace_all.get_sensitive()
    bar.term.set_text("api")
    settle()
    assert bar._replace_all.get_sensitive()


def test_replace_all_says_how_many_it_changed():
    bar = FindBar()
    bar.search_in(searching("api api api\n"))
    bar.term.set_text("api")
    bar.replacement.set_text("worker")
    settle()
    assert bar.replace_all() == 3
    assert "3 replaced" in bar.count


def test_matching_is_case_insensitive_until_told_otherwise():
    bar = FindBar()
    bar.search_in(searching("API api\n"))
    bar.term.set_text("api")
    settle()
    assert "2" in bar.count
    bar._case.set_active(True)
    settle()
    assert "1" in bar.count


def test_a_regular_expression_is_honoured_when_asked_for():
    bar = FindBar()
    bar.search_in(searching("a1 b2 c3\n"))
    bar._regex.set_active(True)
    bar.term.set_text(r"[a-c]\d")
    settle()
    assert "3" in bar.count


def test_with_no_file_the_row_reports_nothing_rather_than_failing():
    bar = FindBar()
    bar.search_in(None)
    bar.term.set_text("anything")
    assert bar.count == ""


def test_opening_find_with_no_file_says_so_and_stays_shut():
    window = Window()
    said: list[str] = []
    window._say = said.append
    window.show_find()
    assert said and "Open a file" in said[0]
    assert not window._find.get_visible()


def test_find_opens_over_the_file_and_escape_closes_it():
    window = Window()
    window.open_workspace(WORKSPACE)
    window.open_file(sorted(WORKSPACE.rglob("*.tf"))[0])
    window.activate_action("win.find", None)
    assert window._find.get_visible()
    window._find.close()
    assert not window._find.get_visible()


def test_each_file_searches_itself():
    """A highlight from one file must not follow you into another."""
    window = Window()
    window.open_workspace(WORKSPACE)
    files = sorted(WORKSPACE.rglob("*.tf"))[:2]
    for path in files:
        window.open_file(path, preview=False)
    pages = [window._files_open.pages[path.resolve()] for path in files]
    assert pages[0].search is not pages[1].search
