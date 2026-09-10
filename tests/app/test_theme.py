"""The design system's own rules, held as tests.

`docs/design-system.md` states them; these are the ones a machine can check.
The one idea is that colour encodes **consequence**, not category, and that
there are four levels and no fifth.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backsight.app.theme import tokens

COMPONENTS = Path(__file__).resolve().parents[2] / "src" / "backsight" / "app" / "theme"
SHEET = COMPONENTS / "components.css"


def test_every_token_exists_in_both_modes():
    """A half-added token renders as transparent black rather than failing."""
    tokens.check_parity()


def test_there_are_four_consequence_levels_and_no_fifth():
    """Six severities means nobody reads any of them."""
    families = {name.split("_")[1] for name in tokens.LIGHT if name.startswith("consequence_")}
    assert families == {"safe", "disruptive", "irreversible"}
    # Blocked is the fourth and shares irreversible's hue on purpose.
    assert "blocked_text" in tokens.LIGHT


def test_blocked_and_irreversible_share_a_hue():
    """They are told apart by treatment, not colour — blocked fills its card.

    The text and the edge are the same value in both, which is what "same hue"
    means. The backgrounds are not, and that is the treatment: irreversible's
    is a tint behind a border, blocked's is the fill of a whole card, and a
    fill has to be deeper than a tint or the difference does not read.
    """
    for palette in (tokens.LIGHT, tokens.DARK):
        assert palette["blocked_text"] == palette["consequence_irreversible_text"]
        assert palette["blocked_edge"] == palette["consequence_irreversible_edge"]
        assert palette["blocked_bg"] != palette["consequence_irreversible_bg"]


def test_only_the_blocker_fills_its_whole_card():
    """The difference between "this is dangerous" and "this will not run"."""
    css = SHEET.read_text()
    filled = re.findall(r"\.tf-blocker\s*\{[^}]*background-color: @tf_blocked_bg", css)
    assert filled
    group = re.search(r"\.tf-group\.tf-irreversible\s*\{([^}]*)\}", css)
    assert group is not None
    assert "background" not in group.group(1)
    # A rule down the left edge, never a box: a boxed card reads as a container
    # of equal weight to its neighbours, and a rule reads as a spine.
    assert "border-left-color" in group.group(1)


def test_apply_is_neutral_until_the_plan_is_irreversible():
    """A permanently red Apply button trains people to ignore red."""
    css = SHEET.read_text()
    plain = re.search(r"button\.tf-apply\s*\{([^}]*)\}", css)
    assert plain is not None
    assert "@tf_accent_fill" in plain.group(1)
    assert re.search(
        r"button\.tf-apply\.tf-irreversible\s*\{[^}]*@tf_consequence_irreversible_fill", css
    )


def test_no_literal_colour_appears_in_the_components():
    """If a value is needed it goes in tokens.py, in both palettes."""
    css = SHEET.read_text()
    literals = re.findall(r"#[0-9a-fA-F]{3,8}\b", css)
    assert literals == []
    assert "rgb(" not in css


def test_the_component_sheet_only_names_tokens_that_exist():
    """A colour that is never defined renders as nothing, silently."""
    css = SHEET.read_text()
    used = {name for name in re.findall(r"@(tf_[a-z_]+)", css)}
    defined = {f"tf_{name}" for name in tokens.LIGHT}
    assert used <= defined, f"not in the palette: {sorted(used - defined)}"


def test_accent_is_never_used_to_say_something_is_fine():
    """Safe already means that. Accent marks the current thing, not a verdict."""
    css = SHEET.read_text()
    for rule in re.findall(r"\.tf-(?:safe|chip\.tf-safe)[^{]*\{([^}]*)\}", css):
        assert "accent" not in rule


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_the_sheet_defines_every_token_and_the_adwaita_bridge(mode: str):
    css = tokens.define_colors(mode)
    for name in tokens.LIGHT:
        assert f"@define-color tf_{name} " in css
    for adw in tokens.ADWAITA_MAP:
        assert f"@define-color {adw} " in css


def test_the_bridge_only_points_at_tokens_that_exist():
    for token in tokens.ADWAITA_MAP.values():
        assert token in tokens.LIGHT
        assert token in tokens.DARK


def test_two_weights_only():
    """Anything at 600 or above reads heavy against GTK chrome."""
    assert set(tokens.WEIGHT.values()) == {400, 500}
    css = SHEET.read_text()
    for weight in re.findall(r"font-weight:\s*(\d+)", css):
        assert int(weight) in (400, 500)


def test_single_sided_borders_are_not_rounded():
    """Rounded corners need a border on all four sides."""
    css = SHEET.read_text()
    for body in re.findall(r"\{([^}]*)\}", css):
        sided = re.search(r"border-(left|right|top|bottom):", body)
        if not sided or "border:" in body:
            continue
        radius = re.search(r"border-radius:\s*([^;]+);", body)
        if radius is not None:
            assert radius.group(1).strip() in ("0", "999px"), body


def test_the_editor_schemes_are_generated_from_the_tokens():
    """A hand-written scheme drifts from the palette the moment either moves."""
    from backsight.app.theme import schemes

    for mode in ("light", "dark"):
        written = schemes.scheme(mode)
        palette = tokens.DARK if mode == "dark" else tokens.LIGHT
        assert palette["syn_type"] in written
        assert palette["plan_replace"] in written
        assert "do not edit" in written.lower()


def test_the_scheme_files_on_disk_match_what_the_generator_produces():
    """They are committed because GtkSourceView loads them from a path."""
    from backsight.app.theme import schemes

    for mode in ("light", "dark"):
        path = schemes.SCHEMES / f"backsight-{mode}.xml"
        assert path.read_text() == schemes.scheme(mode), "regenerate the schemes"


def test_a_resource_type_and_its_name_never_share_a_colour():
    from backsight.app.theme import schemes

    for mode in ("light", "dark"):
        written = schemes.scheme(mode)
        title = re.search(r'block-title"\s+foreground="(\w+)"', written)
        label = re.search(r'block-label"\s+foreground="(\w+)"', written)
        assert title and label and title.group(1) != label.group(1)


def test_one_theme_per_display():
    """Two on one display is two provider sets at the same priority, and which
    stylesheet wins then depends on construction order."""
    from backsight.app.theme import Theme

    assert Theme.shared() is Theme.shared()


def test_the_application_installs_it_before_any_window_exists():
    """Stock widgets keep libadwaita's greys until the tokens are in."""
    import inspect

    from backsight.app.application import Application

    source = inspect.getsource(Application.do_startup)
    assert "Theme.shared()" in source


def test_the_stylesheet_never_uses_point_sizes():
    """GTK scales pt by the text factor a second time on some setups."""
    import re
    from pathlib import Path

    css = Path("src/backsight/app/theme/components.css").read_text()
    assert not re.search(r"\d+pt\b", css)


def test_only_two_weights_exist():
    """600 and 700 read heavy against GTK chrome. More emphasis is a size up."""
    import re
    from pathlib import Path

    css = Path("src/backsight/app/theme/components.css").read_text()
    used = set(re.findall(r"font-weight:\s*(\S+?);", css))
    assert used <= {"400", "500"}, used
