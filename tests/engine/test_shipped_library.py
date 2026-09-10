"""What ships with the application, checked as Terraform rather than as text.

A library with nothing in it is a mechanism rather than a feature, and the
first thing anybody does is look. These are the language constructs people get
wrong — and an entry that does not parse is worse than no entry, because
somebody inserts it and then has to work out whose fault it is.
"""

from __future__ import annotations

import pytest

from backsight.engine.hcl.navigation import blocks
from backsight.engine.library.entry import Kind, Source
from backsight.engine.library.placeholders import resolve
from backsight.engine.library.store import SHIPPED, load, read_directory

SHIPPED_ENTRIES, SHIPPED_BROKEN = read_directory(SHIPPED, Source.BUILT_IN)


def test_there_is_something_in_it():
    assert len(SHIPPED_ENTRIES) >= 10


def test_every_shipped_file_reads_as_an_entry():
    assert SHIPPED_BROKEN == [], [str(one.path) for one in SHIPPED_BROKEN]


@pytest.mark.parametrize("entry", SHIPPED_ENTRIES, ids=lambda e: e.name)
def test_it_parses_as_terraform_once_the_placeholders_are_filled(entry):
    """An entry that does not parse is worse than no entry: somebody inserts
    it and then has to work out whose fault it is."""
    if entry.kind is Kind.RUNBOOK:
        pytest.skip("a runbook is prose and steps, not one file of HCL")
    text = resolve(entry.body).text
    assert blocks(text.encode("utf-8")), text


@pytest.mark.parametrize("entry", SHIPPED_ENTRIES, ids=lambda e: e.name)
def test_every_one_says_what_it_is_for(entry):
    assert entry.about, entry.name
    assert entry.tags, entry.name


@pytest.mark.parametrize("entry", SHIPPED_ENTRIES, ids=lambda e: e.name)
def test_none_of_them_shouts_or_apologises(entry):
    """The words on the cut list, and the ones that pad without saying."""
    said = f"{entry.name} {entry.about} {entry.body}".lower()
    for word in ("please", "simply", "just ", "easy", "successfully", "seamless"):
        assert word not in said, f"{entry.name} says {word!r}"


@pytest.mark.parametrize("entry", SHIPPED_ENTRIES, ids=lambda e: e.name)
def test_nothing_in_them_is_real(entry):
    """Everything shipped is invented. A plausible account number in a snippet
    is one somebody pastes into a bucket name."""
    said = entry.body
    assert "amazonaws.com/" not in said
    for digits in range(0, 10):
        assert str(digits) * 12 not in said


def test_the_runbooks_read_as_ordered_steps():
    runbooks = [entry for entry in SHIPPED_ENTRIES if entry.kind is Kind.RUNBOOK]
    assert runbooks
    for entry in runbooks:
        assert len(entry.steps) >= 3, entry.name
        assert all(step.title for step in entry.steps)


def test_a_runbook_step_that_names_a_command_names_a_real_one():
    for entry in SHIPPED_ENTRIES:
        for step in entry.steps:
            if step.is_a_command:
                assert step.command.startswith("tofu "), step.command


def test_the_meta_constructs_people_get_wrong_are_all_there():
    names = " ".join(entry.name for entry in SHIPPED_ENTRIES).lower()
    for wanted in ("moved", "import", "for_each", "dynamic", "lifecycle", "count"):
        assert wanted in names, wanted


def test_they_arrive_in_a_library_nobody_configured(tmp_path):
    found = load(home=tmp_path)
    assert len(found) >= 10
    assert all(entry.source is Source.BUILT_IN for entry in found.entries)


def test_your_own_still_wins_over_one_that_ships(tmp_path):
    from backsight.engine.library.store import yours

    where = yours(tmp_path)
    where.mkdir(parents=True)
    (where / "mine.tf").write_text("# name: moved block\n\nmoved {}\n", encoding="utf-8")
    found = load(home=tmp_path)
    assert found.named("moved block").source is Source.YOURS
