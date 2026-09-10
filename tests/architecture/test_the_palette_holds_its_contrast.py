"""Every text token clears WCAG AA on every surface it can land on.

The design system carries a checker that **fails rather than warns**, and it
runs against `tokens.json` in the design folder. That folder is gitignored, so
this is the same rule asserted against the palette the application actually
ships — otherwise the guarantee lives somewhere no commit can reach.

It caught twenty-four failures the first time it was run over the proposed
palette, and every one of them was solved by moving the colour rather than by
lowering the bar.
"""

from __future__ import annotations

import pytest

from backsight.app.theme import tokens

# 4.5:1 for text, 3:1 for a control's edge or a mark that is not read as words.
TEXT = 4.5
NON_TEXT = 3.0

# The raised surfaces, worst first. **A token is held against every ground it
# can actually land on, not against a list of all of them** — a syntax colour
# that has to clear the rail's background is a colour solved against a problem
# nobody has, and solving it costs the buffer something real.
SURFACES = ("canvas", "surface", "panel", "overlay")

# Read as words, so 4.5:1.
INK = (
    "ink",
    "ink_muted",
    "ink_faint",
    "consequence_safe_text",
    "consequence_disruptive_text",
    "consequence_irreversible_text",
    "blocked_text",
    "accent_text",
)

# Only ever drawn in the buffer, which is `panel`. Nothing highlights HCL on a
# header bar.
SYNTAX = (
    "syn_block",
    "syn_type",
    "syn_name",
    "syn_attr",
    "syn_string",
    "syn_number",
    "syn_fn",
    "syn_interp",
    "syn_comment",
    "syn_operator",
    "syn_invalid",
)

# The one recessed surface — a console transcript, a filter field. Only body
# text lands in it, and **the quietest ink is not allowed there**: `ink_faint`
# comes to 4.19:1 on it, and the well cannot be lightened enough to fix that
# without ceasing to be a well. `components.css` steps it up to `ink_muted`
# inside one, which is the rule this asserts the palette can keep.
IN_A_WELL = ("ink", "ink_muted")

# A mark or an edge rather than a word, so 3:1.
MARKS = (
    "consequence_safe_edge",
    "consequence_disruptive_edge",
    "consequence_irreversible_edge",
    "blocked_edge",
    "accent_edge",
    "focus_ring",
    "plan_create",
    "plan_update",
    "plan_replace",
    "plan_destroy",
)

# Never read against a surface: `ink_ghost` is a placeholder and a disabled
# glyph, `plan_noop` is a mark for something that will not happen, and the
# hairlines are a rule rather than a thing. Exempt by a written ruling rather
# than by being left off a list nobody reads.
EXEMPT = ("ink_ghost", "plan_noop", "hairline", "hairline_strong")


def channel(value: float) -> float:
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def luminance(colour: str) -> float:
    said = colour.lstrip("#")
    red, green, blue = (channel(int(said[at : at + 2], 16) / 255) for at in (0, 2, 4))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(one: str, other: str) -> float:
    first, second = sorted((luminance(one), luminance(other)), reverse=True)
    return (first + 0.05) / (second + 0.05)


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("token", INK)
def test_every_text_token_is_readable_on_every_surface(mode: str, token: str):
    palette = tokens.DARK if mode == "dark" else tokens.LIGHT
    for surface in SURFACES:
        found = contrast(palette[token], palette[surface])
        assert found >= TEXT, f"{mode} {token} on {surface} is {found:.2f}:1, needs {TEXT}"


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("token", SYNTAX)
def test_every_syntax_colour_is_readable_in_the_buffer(mode: str, token: str):
    palette = tokens.DARK if mode == "dark" else tokens.LIGHT
    found = contrast(palette[token], palette["panel"])
    assert found >= TEXT, f"{mode} {token} on the buffer is {found:.2f}:1, needs {TEXT}"


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("token", IN_A_WELL)
def test_what_goes_in_a_well_is_readable_in_it(mode: str, token: str):
    palette = tokens.DARK if mode == "dark" else tokens.LIGHT
    found = contrast(palette[token], palette["sunken"])
    assert found >= TEXT, f"{mode} {token} on sunken is {found:.2f}:1, needs {TEXT}"


def test_the_quietest_ink_is_stepped_up_inside_a_well():
    """The rule the palette cannot keep on its own, kept in the sheet instead."""
    from pathlib import Path as _Path

    sheet = (
        _Path(__file__).resolve().parents[2]
        / "src"
        / "backsight"
        / "app"
        / "theme"
        / "components.css"
    ).read_text(encoding="utf-8")
    assert ".tf-sunken .tf-faint { color: @tf_ink_muted; }" in sheet


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("token", MARKS)
def test_every_mark_is_visible_on_every_surface(mode: str, token: str):
    palette = tokens.DARK if mode == "dark" else tokens.LIGHT
    for surface in SURFACES:
        found = contrast(palette[token], palette[surface])
        assert found >= NON_TEXT, f"{mode} {token} on {surface} is {found:.2f}:1, needs {NON_TEXT}"


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_white_on_every_fill_is_readable(mode: str):
    """A filled button's label. `ink_on_fill` is white in both modes, so the
    fill is what has to be dark enough rather than the text light enough."""
    palette = tokens.DARK if mode == "dark" else tokens.LIGHT
    for token in (
        "consequence_safe_fill",
        "consequence_disruptive_fill",
        "consequence_irreversible_fill",
        "blocked_fill",
        "accent_fill",
    ):
        found = contrast(palette["ink_on_fill"], palette[token])
        assert found >= TEXT, f"{mode} ink_on_fill on {token} is {found:.2f}:1"


def test_the_exemptions_are_named_rather_than_left_off_a_list():
    """A rule with a silent exception is a rule nobody can audit."""
    checked = set(INK) | set(SYNTAX) | set(MARKS) | set(SURFACES)
    for token in EXEMPT:
        assert token in tokens.LIGHT
        assert token not in checked
