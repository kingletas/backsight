"""Editor text size: the most commonly missed shortcut, and remembered."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.settings.zoom import LARGEST, SMALLEST, Zoom, read, remember

BASE = 12.5


def test_the_default_is_the_size_the_scale_says():
    """A step, not a size, so changing the design token moves every level."""
    assert Zoom(base=BASE).size == BASE
    assert Zoom(base=BASE).is_default


def test_a_step_up_is_larger_and_a_step_down_is_smaller():
    assert Zoom(base=BASE).bigger().size > BASE
    assert Zoom(base=BASE).smaller().size < BASE


def test_stepping_up_and_back_down_returns_to_where_it_was():
    assert Zoom(base=BASE).bigger().smaller().size == BASE


def test_reset_goes_back_however_far_it_travelled():
    zoom = Zoom(base=BASE)
    for _ in range(6):
        zoom = zoom.bigger()
    assert zoom.reset().size == BASE
    assert zoom.reset().is_default


def test_it_stops_rather_than_pretending_to_move():
    """A step that did nothing must be reported, not swallowed."""
    zoom = Zoom(base=BASE)
    for _ in range(40):
        zoom = zoom.bigger()
    assert zoom.size == LARGEST
    assert zoom.bigger() is zoom

    zoom = Zoom(base=BASE)
    for _ in range(40):
        zoom = zoom.smaller()
    assert zoom.size == SMALLEST
    assert zoom.smaller() is zoom


def test_a_step_feels_the_same_at_every_size():
    """A ratio rather than a number of pixels."""
    small = Zoom(base=9.0)
    large = Zoom(base=24.0)
    assert small.bigger().size / small.size == round(large.bigger().size / large.size, 2)


def test_the_level_survives_a_restart(tmp_path: Path):
    remember(Zoom(base=BASE, steps=3), home=tmp_path)
    assert read(BASE, home=tmp_path).steps == 3


def test_never_zoomed_reads_as_the_design_size(tmp_path: Path):
    assert read(BASE, home=tmp_path).is_default


def test_an_unreadable_file_costs_the_zoom_and_nothing_else(tmp_path: Path):
    from backsight.engine.settings.zoom import FILE, directory

    path = directory(home=tmp_path) / FILE
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")
    assert read(BASE, home=tmp_path).is_default
