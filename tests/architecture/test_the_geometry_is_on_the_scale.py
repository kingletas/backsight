"""Every length in the stylesheet comes off the token scale, and the scale
matches the design's.

**The scale was forked before this test existed.** `theme/tokens.py` said
spacing `2xl: 20` where the design said 24, radius `card: 10` where it said 8,
and `components.css` carried fifteen paddings that were on neither scale —
7px, 9px, 10px, 11px, 14px. Nothing compared the two, so each edit to either
widened the gap in silence.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backsight.app.theme import tokens

ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = ROOT / "src" / "backsight" / "app" / "theme" / "components.css"
DESIGN = ROOT / "local.d" / "design" / "v2" / "tokens.css"

# A one-pixel rule is a border, not a step on a spacing scale.
NOT_SPACING = {0, 1}


def _lengths(declaration: str) -> list[int]:
    return [int(found) for found in re.findall(r"(\d+)px", declaration)]


def _declarations(names: str) -> list[tuple[int, str]]:
    said = COMPONENTS.read_text(encoding="utf-8").splitlines()
    pattern = re.compile(rf"\b({names})\s*:\s*([^;}}]+)")
    return [
        (at + 1, found.group(2).strip())
        for at, line in enumerate(said)
        for found in [pattern.search(line)]
        if found
    ]


def test_every_spacing_length_is_on_the_scale():
    allowed = set(tokens.SPACE.values())
    for line, declaration in _declarations("padding|margin|gap"):
        for length in _lengths(declaration):
            if length in NOT_SPACING:
                continue
            assert length in allowed, (
                f"components.css:{line} spaces by {length}px, which is not on the scale "
                f"{sorted(allowed)}"
            )


def test_every_radius_is_on_the_scale():
    allowed = set(tokens.RADIUS.values())
    for line, declaration in _declarations("border-radius"):
        for length in _lengths(declaration):
            assert length in allowed, (
                f"components.css:{line} rounds by {length}px, which is not a radius token "
                f"{sorted(allowed)}"
            )


@pytest.mark.skipif(not DESIGN.exists(), reason="the design folder is not on this machine")
def test_the_scale_is_the_one_the_design_publishes():
    """The design folder is gitignored, so this checks when it is there and
    says nothing when it is not — a clone still passes, and this machine cannot
    drift."""
    said = DESIGN.read_text(encoding="utf-8")
    published = {
        name: int(value)
        for name, value in re.findall(r"--(space-[\w-]+|radius-[\w-]+):\s*(\d+)", said)
    }
    for group, scale in (("space", tokens.SPACE), ("radius", tokens.RADIUS)):
        for name, value in scale.items():
            theirs = published[f"{group}-{name}"]
            assert theirs == value, f"{group}-{name}: design says {theirs}, we say {value}"
