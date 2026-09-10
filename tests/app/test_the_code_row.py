"""The code row is the height the design asks for, in pixels.

**GTK means something else by `line-height`.** On the web it multiplies the
font size; GTK multiplies the font's own natural line box, which for a
monospace is already about 1.43 of its size. So `line-height: 1.45` in the
stylesheet produced a 23px row where the design's arithmetic says 16 — and no
amount of checking the stylesheet would have shown it.
"""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import Gtk  # noqa: E402

from backsight.app.leading import apply_leading, natural_line, wanted_row  # noqa: E402


@pytest.fixture
def view():
    return Gtk.TextView()


def test_the_row_is_the_font_size_times_the_leading(view):
    row = apply_leading(view, 1.45)
    assert row == wanted_row(view, 1.45)


def test_a_row_is_never_shorter_than_the_glyphs_in_it(view):
    """A leading below the font's own line box cannot clip the text."""
    row = apply_leading(view, 0.5)
    assert row >= natural_line(view)
    assert view.get_pixels_above_lines() == 0
    assert view.get_pixels_below_lines() == 0


def test_extra_space_is_split_above_and_below(view):
    apply_leading(view, 3.0)
    above = view.get_pixels_above_lines()
    below = view.get_pixels_below_lines()
    assert above and below
    assert abs(above - below) <= 1


def test_a_looser_leading_makes_a_taller_row(view):
    tight = apply_leading(view, 1.45)
    loose = apply_leading(view, 2.5)
    assert loose > tight


def test_the_stylesheet_no_longer_sets_a_line_height_on_the_buffer():
    """Two places setting the row is how they disagree."""
    from pathlib import Path

    theme = Path(__file__).resolve().parents[2] / "src" / "backsight" / "app" / "theme"
    said = (theme / "__init__.py").read_text(encoding="utf-8")
    assert "line-height" not in said.split("_apply_zoom")[1].split("def ")[0]


def test_zooming_recomputes_the_row_for_every_open_file():
    """A new font size needs the row computed again, or it keeps the old one."""
    from pathlib import Path

    from backsight.app.window import Window

    root = Path(__file__).resolve().parents[2] / "fixtures" / "workspace"
    window = Window()
    window.open_workspace(root)
    window.open_file(root / "environments" / "prod" / "main.tf")
    assert window._files_open.every_page(), "the fixture should leave a file open"
    # The zoom path must reach the pages rather than only the stylesheet.
    window.zoom(1)
    window.zoom(0)
