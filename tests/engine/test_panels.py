"""The bottom panel is sized by its content, within bounds."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.settings.panels import (
    DRAGS_TO,
    GROWS_TO,
    LEAST,
    first_height,
    height_for,
    read,
    remember,
)


def test_a_small_panel_gets_only_what_it_asked_for():
    """One diagnostic should not take half the window."""
    assert height_for(wanted=200, window=1000) == 200


def test_it_is_capped_rather_than_allowed_to_take_the_window():
    assert height_for(wanted=900, window=1000) == int(1000 * GROWS_TO)


def test_it_never_shrinks_below_a_heading_and_a_sentence():
    assert height_for(wanted=10, window=1000) == LEAST


def test_a_window_too_small_for_the_floor_gets_the_cap_instead():
    """The floor may not push the panel past its own ceiling."""
    assert height_for(wanted=500, window=200) == int(200 * GROWS_TO)


def test_no_window_yet_is_not_a_reason_to_guess_large():
    assert height_for(wanted=900, window=0) == LEAST


def test_a_dragged_height_comes_back(tmp_path: Path):
    remember("/src/acme", 410, home=tmp_path)
    assert read("/src/acme", home=tmp_path) == 410


def test_each_workspace_keeps_its_own(tmp_path: Path):
    remember("/src/acme", 410, home=tmp_path)
    remember("/src/data", 220, home=tmp_path)
    assert read("/src/acme", home=tmp_path) == 410
    assert read("/src/data", home=tmp_path) == 220


def test_a_workspace_never_dragged_has_no_opinion(tmp_path: Path):
    assert read("/src/never-opened", home=tmp_path) is None


def test_an_unreadable_file_costs_the_height_and_nothing_else(tmp_path: Path):
    from backsight.engine.settings.panels import FILE, directory

    path = directory(home=tmp_path) / FILE
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")
    assert read("/src/acme", home=tmp_path) is None
    remember("/src/acme", 300, home=tmp_path)
    assert read("/src/acme", home=tmp_path) == 300


# --- the two ceilings, and the height it opens at --------------------------


def test_content_stops_growing_at_the_lower_ceiling():
    """A panel growing itself must not decide it matters more than the file."""
    assert height_for(wanted=900, window=1000) == int(1000 * GROWS_TO)


def test_a_height_somebody_dragged_to_is_allowed_further():
    assert height_for(wanted=900, window=1000, dragged=True) == int(1000 * DRAGS_TO)


def test_even_a_drag_stops_short_of_the_whole_window():
    """A drawer that fills the window is a screen, and a screen needs a way back."""
    assert height_for(wanted=10_000, window=1000, dragged=True) == 700


def test_it_opens_at_the_same_fraction_every_time():
    assert first_height(1000) == 380


def test_it_never_opens_below_the_floor():
    assert first_height(200) == LEAST
