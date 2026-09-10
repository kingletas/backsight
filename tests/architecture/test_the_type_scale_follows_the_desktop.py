"""No size in the stylesheet is a pixel count, and the ratios match the tokens.

A px font size does not follow the desktop's text scaling factor. Measured: at
2x scaling a 13px label does not move and a 1em label doubles — so somebody who
has set 150% for accessibility saw no change anywhere in this application, and
the 11px status bar, gutter and rail metadata are exactly where it would have
mattered most.

`requirements.md` asks for the setting to be respected and `typography.md` says
to use px rather than pt. Both are right on their own; `em` is what satisfies
them together, because it is scaled once by the factor meant to scale it.
"""

from __future__ import annotations

import re
from pathlib import Path

from backsight.app.theme import tokens

SHEET = (
    Path(__file__).resolve().parents[2] / "src" / "backsight" / "app" / "theme" / "components.css"
)


def sizes() -> list[str]:
    return re.findall(r"font-size:\s*([^;]+);", SHEET.read_text(encoding="utf-8"))


def test_no_font_size_is_given_in_pixels():
    said = [size for size in sizes() if size.strip().endswith("px")]
    assert said == [], "px font sizes are deaf to text scaling: " + ", ".join(said)


def test_none_of_them_is_in_points_either():
    """`pt` is scaled a second time on some setups, which is what typography.md
    is protecting against."""
    assert [size for size in sizes() if size.strip().endswith("pt")] == []


def test_every_ratio_in_the_sheet_is_one_the_tokens_produce():
    """The design lives in `TYPE`; the sheet says the same numbers a second
    time, and two representations that can drift is why this is checked."""
    known = {f"{tokens.ratio_of(size)}em" for size in tokens.TYPE.values()}
    known.add(f"{tokens.density()}em")
    unknown = sorted({size.strip() for size in sizes()} - known)
    assert unknown == [], f"sizes with no token behind them: {unknown}"


def test_the_body_size_is_the_one_everything_else_is_a_ratio_of():
    assert tokens.ratio("body") == 1.0
    assert tokens.ratio("micro") < 1.0
    assert tokens.ratio("figure") > 1.0


def test_the_density_says_this_design_is_tighter_than_the_desktop():
    """Written as a ratio so the decision survives somebody scaling up."""
    assert 0 < tokens.density() < 1
