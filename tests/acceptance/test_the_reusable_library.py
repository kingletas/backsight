"""Finding a block and putting it in the file — the complaint this answers.

"I shouldn't have to type the same terraform block 20x times." So the measure
is the path: type a word, press Return, it is in the file with the first field
selected, and no click anywhere in that.
"""

from __future__ import annotations

import pytest

from tests.acceptance.looking import drawn, says, settle

gi = pytest.importorskip("gi", reason="the toolkit is not installed")


def test_the_library_is_never_empty(opened):
    """A library with nothing in it is a mechanism rather than a feature, and
    the first thing anybody does is look."""
    opened.show_library()
    settle(opened)
    assert len(opened.library) >= 10
    assert drawn(opened.library_panel)


def test_typing_a_word_narrows_it(opened):
    opened.show_library("moved")
    settle(opened)
    assert opened.library_panel.showing
    assert any("moved" in one.name.lower() for one in opened.library_panel.showing)


def test_return_puts_the_best_match_in_the_file(opened):
    """No click anywhere in that path, because a click is one more thing than
    typing the block again was supposed to cost."""
    page = opened._files_open.current
    before = page.text()
    opened.show_library("moved block")
    settle(opened)
    opened.library_panel.search.emit("activate")
    settle(opened, 0.4)
    assert "moved {" in page.text()
    assert page.text() != before


def test_and_selects_the_first_thing_to_fill_in(opened):
    opened.show_library("moved block")
    settle(opened)
    opened.library_panel.search.emit("activate")
    settle(opened, 0.4)
    assert opened._stops is not None and opened._stops.is_live
    bounds = opened._files_open.current.buffer.get_selection_bounds()
    assert bounds


def test_hcl_interpolation_arrives_intact(opened):
    """The reason the toolkit's own snippet engine cannot be used."""
    page = opened._files_open.current
    page.buffer.set_text("")
    opened.insert_entry(
        type("E", (), {"name": "x", "body": 'bucket = "${1:acme}-${var.environment}"\n'})()
    )
    settle(opened, 0.3)
    assert page.text().strip() == 'bucket = "acme-${var.environment}"'


def test_saving_the_selection_keeps_it(opened):
    """The most useful entry anybody has is the block in front of them."""
    before = len(opened.library)
    opened._keep("My whole file", opened._files_open.current.text())
    settle(opened, 0.3)
    assert len(opened.library) == before + 1
    assert opened.library.named("My whole file") is not None


def test_and_it_is_found_again_by_searching(opened):
    opened._keep("A bucket I wrote", 'resource "aws_s3_bucket" "mine" {}\n')
    settle(opened, 0.3)
    opened.show_library("bucket I wrote")
    settle(opened, 0.3)
    assert [one.name for one in opened.library_panel.showing] == ["A bucket I wrote"]


def test_a_runbook_is_read_rather_than_inserted(opened):
    opened.show_library("Recover from an apply")
    settle(opened)
    found = opened.library_panel.showing
    assert found
    opened.library_panel._choose(found[0])
    settle(opened, 0.3)
    assert opened.library_panel._steps.get_visible()
    assert found[0].steps


def test_every_shipped_entry_is_terraform_that_parses(opened):
    """An entry that does not parse is worse than no entry: somebody inserts
    it and then works out whose fault it is."""
    from backsight.engine.hcl.navigation import blocks
    from backsight.engine.library.entry import Kind
    from backsight.engine.library.placeholders import resolve

    for entry in opened.library.entries:
        if entry.kind is Kind.RUNBOOK or not entry.body.strip():
            continue
        assert blocks(resolve(entry.body).text.encode("utf-8")), entry.name


def test_the_library_says_what_would_fill_it_when_a_search_finds_nothing(opened):
    opened.show_library("kubernetes helm chart")
    settle(opened)
    assert says(opened.library_panel, "Nothing matches that")
