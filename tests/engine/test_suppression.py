"""A suppression is a deferral with a date, never a permanent silence."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from backsight.engine.insight.suppression import (
    LONGEST,
    Suppression,
    add,
    location,
    read,
)

TODAY = date(2026, 9, 7)


def test_a_workspace_that_suppresses_nothing_is_not_a_problem(tmp_path):
    assert read(tmp_path).entries == []


def test_a_suppression_round_trips(tmp_path):
    add(
        tmp_path,
        Suppression("aws_sg.db", "exposure", TODAY + timedelta(days=30), "waiting on the VPC"),
        on=TODAY,
    )
    found = read(tmp_path).entries
    assert len(found) == 1
    assert found[0].address == "aws_sg.db"
    assert found[0].reason == "waiting on the VPC"


def test_an_expiry_in_the_past_hides_nothing(tmp_path):
    with pytest.raises(ValueError, match="already expired"):
        add(tmp_path, Suppression("a", "exposure", TODAY - timedelta(days=1)), on=TODAY)


def test_a_suppression_cannot_last_forever(tmp_path):
    """A permanent one stops being a decision and becomes a fact of the code."""
    with pytest.raises(ValueError, match="at most"):
        add(tmp_path, Suppression("a", "exposure", TODAY + LONGEST + timedelta(days=1)), on=TODAY)


def test_an_expired_suppression_stops_hiding_the_finding(tmp_path):
    add(tmp_path, Suppression("a", "exposure", TODAY + timedelta(days=1)), on=TODAY)
    found = read(tmp_path)
    assert found.hides("a", "exposure", TODAY)
    assert not found.hides("a", "exposure", TODAY + timedelta(days=2))
    assert found.expired(TODAY + timedelta(days=2))


def test_an_entry_with_no_expiry_is_not_a_suppression(tmp_path):
    """A missing date is not "forever"; it is a broken entry."""
    path = location(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text('[[suppress]]\naddress = "a"\nfinding = "exposure"\n', encoding="utf-8")
    assert read(tmp_path).entries == []


def test_an_unreadable_file_suppresses_nothing(tmp_path):
    """The safe failure is to show findings, never to hide them."""
    path = location(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("[[suppress\nbroken", encoding="utf-8")
    assert read(tmp_path).entries == []


def test_the_file_is_committed_with_the_workspace(tmp_path):
    """One that lived on a laptop would be invisible to a reviewer."""
    written = add(tmp_path, Suppression("a", "exposure", TODAY + timedelta(days=7)), on=TODAY)
    assert written.parent.name == ".backsight"
    assert Path(tmp_path) in written.parents


def test_a_quote_in_the_reason_does_not_break_the_file(tmp_path):
    add(
        tmp_path,
        Suppression("a", "exposure", TODAY + timedelta(days=7), 'they said "later"'),
        on=TODAY,
    )
    assert read(tmp_path).entries[0].reason == 'they said "later"'


def test_a_second_suppression_does_not_replace_the_first(tmp_path):
    for name in ("a", "b"):
        add(tmp_path, Suppression(name, "exposure", TODAY + timedelta(days=7)), on=TODAY)
    assert len(read(tmp_path).entries) == 2
