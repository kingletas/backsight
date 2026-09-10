"""Design tokens for the Terraform workspace editor.

This module is the single source of truth. The GTK stylesheets are generated
from it, so a value is edited here and nowhere else.

Why generated: GTK4 CSS cannot redefine @define-color per selector, so light
and dark must be two separate stylesheets swapped at runtime. Hand-maintaining
two files guarantees drift.

Usage:
    from theme import tokens
    tokens.install(app)          # loads the right sheet, follows the system
    tokens.color("consequence_irreversible_edge")   # Gdk.RGBA, for Cairo

The palette is organised around consequence, not around generic status. A
Terraform change is safe, disruptive, irreversible, or blocked, and every
colour decision in the app resolves to one of those four. Resist adding a
fifth: the moment there are six severities nobody reads any of them.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Scale
# ---------------------------------------------------------------------------

# 4px grid. Tool UI is dense; these are deliberately tighter than Adwaita's
# defaults, which are tuned for touch-adjacent consumer apps.
SPACE = {
    "hair": 2,
    "xs": 4,
    "sm": 6,
    "md": 8,
    "lg": 12,
    "xl": 16,
    "2xl": 24,
    "3xl": 32,
}

RADIUS = {
    "control": 5,  # buttons, inputs, pills in a row
    "card": 8,  # grouped panels, the consequence cards
    "pill": 999,  # status chips only
    "flush": 0,  # anything with a single-sided accent border
}

# Base 13px. Every size is a whole number except the code size: a fractional
# size rounds unpredictably at fractional display scales, and two labels at one
# nominal size can then land a pixel apart.
TYPE = {
    "micro": 11,  # verdict line, gutter line numbers, metadata
    "small": 12,  # secondary UI, tree rows, the annotation lane
    "body": 13,  # default UI text
    # The content must not be smaller than its frame. A monospace at 13 reads
    # visibly smaller than a sans at 13, and 14 costs a line of density — so
    # this is the one size that is allowed a half, and it lives alone in a
    # surface where nothing sits beside it to disagree.
    "code": 13.5,  # editor buffer
    "strong": 15,  # panel headings, resource addresses in review
    "title": 19,  # screen titles — one clear step above strong
    "figure": 26,  # the one big number (cost delta)
}

# Two weights. 500 is the bold; 600+ reads heavy against GTK chrome. Hierarchy
# comes from colour and size, never from a third weight.
WEIGHT = {"regular": 400, "medium": 500}

# The code leading is the density budget of the whole application. At 1.85 a
# 700px buffer held thirty lines; at 1.45 it holds forty, which is a whole
# extra resource block on every screen. Annotations do not live between lines,
# so nothing needs the room back — see app/annotation_lane.py.
LINE = {"tight": 1.25, "body": 1.4, "code": 1.45, "prose": 1.6}

# The line, left to right, in pixels. Reserved whether or not anything is in
# it: a gutter that changes width when a plan finishes moves the code sideways
# under the reader.
GUTTER = {
    # Folding has no API in GtkSourceView 5. The column is held anyway so
    # enabling it later never reflows a file.
    "fold": 12,
    "number": 38,
    "spine": 3,
    "mark": 16,
}

# The strip beside the buffer. Twelve pixels read as an artefact on the
# scrollbar; fourteen reads as a map.
MAP_WIDTH = 14

# Row heights, so two surfaces cannot disagree about how tall a row is.
ROW = {"tab": 28, "rail": 24, "header": 36, "verdict": 24, "drawer_tab": 28}

# What the desktop's own default font comes to in pixels at 96 dpi — GNOME
# ships 11pt. Only used to express this design's density as a ratio of it.
DESKTOP_DEFAULT_PX = 14.67

# Every size above is a px number, and **a px font size does not follow the
# desktop's text scaling factor** — measured: at 2x scaling a 13px label does
# not move and a 1em label doubles. Somebody who has set 150% for accessibility
# saw no change anywhere in this application.
#
# So the scale ships as ratios. `em` is scaled once, by the factor that is meant
# to scale it, which is exactly what typography.md was protecting against `pt`
# doing twice. The numbers above stay the design; these are how they are said.


def density() -> float:
    """The body size as a ratio of the desktop's own.

    This design runs denser than the desktop default on purpose. Written as a
    ratio, that decision survives somebody scaling their whole desktop up.
    """
    return round(TYPE["body"] / DESKTOP_DEFAULT_PX, 3)


def ratio(name: str) -> float:
    """One size as a ratio of the body size, for a CSS `em`."""
    return round(TYPE[name] / TYPE["body"], 3)


def ratio_of(size: float) -> float:
    """Any size in the design's pixels, as a ratio of the body size."""
    return round(size / TYPE["body"], 3)


FONT = {
    # IBM Plex was drawn for technical product UI and pairs its sans and mono
    # on the same skeleton. Inter sits behind it so a machine without Plex
    # lands somewhere drawn for the same job rather than on the desktop default.
    "sans": '"IBM Plex Sans", "Inter", Cantarell, system-ui, sans-serif',
    # JetBrains Mono at 13.5px: drawn tall, l/1/I separate cleanly, the zero is
    # slashed, and the brackets are heavier than the letters — which matters in
    # a language that is mostly braces.
    "mono": '"JetBrains Mono", "IBM Plex Mono", "Source Code Pro", ui-monospace, monospace',
}

# The families this design was drawn against, in the order the stacks above ask
# for them. A font that silently substitutes is a design that silently does not
# exist, so Preferences says which one is actually being used.
WANTED = {"sans": "IBM Plex Sans", "mono": "JetBrains Mono"}


def families(kind: str) -> list[str]:
    """The families in one stack, best first, without the generic fallbacks."""
    generic = {"sans-serif", "serif", "monospace", "system-ui", "ui-monospace", "cursive"}
    said = [name.strip().strip('"') for name in FONT[kind].split(",")]
    return [name for name in said if name.lower() not in generic]


def installed(family: str) -> bool:
    """Whether this machine actually has a family, asked of Pango rather than
    of a package list."""
    from gi.repository import PangoCairo  # noqa: PLC0415

    wanted = family.casefold()
    found = PangoCairo.font_map_get_default().list_families()
    return any(family.get_name().casefold() == wanted for family in found)


def in_use(kind: str) -> tuple[str, bool]:
    """The family that will actually be drawn, and whether it was the one asked for.

    Preferences prints both. Naming a font nobody has, and saying nothing, is
    how every screenshot of this project came to be in a typeface nobody chose.
    """
    stack = families(kind)
    for name in stack:
        if installed(name):
            return name, name == WANTED[kind]
    return "the desktop default", False


DURATION = {"instant": 80, "quick": 140, "settle": 220}

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
# Keys are identical across modes. Anything added to one must be added to both;
# check_parity() enforces it.

LIGHT = {
    # Chrome. Warm neutrals rather than blue-grey, so the amber and red
    # consequence tints do not read as contamination of a cool surface.
    "canvas": "#EFEEEA",  # window background, behind everything
    "surface": "#F6F5F2",  # rail, verdict line, inset panels
    "panel": "#FDFCFA",  # editor buffer, raised cards
    "overlay": "#FFFFFF",  # popovers, menus, dialogs
    "sunken": "#E6E4DF",  # a well something sits in — a filter field, a trough
    "hairline": "rgba(25,24,23,0.11)",
    "hairline_strong": "rgba(25,24,23,0.20)",
    "ink": "#191817",
    "ink_muted": "#54514B",
    "ink_faint": "#6E6B63",
    # The quietest text there is. Never for anything a reader has to read —
    # a placeholder, a disabled glyph, a rule that is nearly a hairline.
    "ink_ghost": "#9C988F",
    "ink_on_fill": "#FFFFFF",
    # Consequence: safe
    "consequence_safe_text": "#3A6612",
    "consequence_safe_bg": "#E9F2DC",
    "consequence_safe_edge": "#6A9338",
    "consequence_safe_fill": "#478016",
    # Consequence: disruptive (recoverable downtime, drift, stale plan)
    "consequence_disruptive_text": "#7E4C07",
    "consequence_disruptive_bg": "#F9ECD6",
    "consequence_disruptive_edge": "#B57C18",
    "consequence_disruptive_fill": "#A0670C",
    # Consequence: irreversible (destroy, replace, no rollback)
    "consequence_irreversible_text": "#9E2A2A",
    "consequence_irreversible_bg": "#FBE9E9",
    "consequence_irreversible_edge": "#DD4847",
    "consequence_irreversible_fill": "#B93636",
    "consequence_irreversible_hover": "#CE3F3C",
    # Blocked is the same hue as irreversible on purpose: both mean stop. They
    # are told apart by treatment, not colour. Blocked fills its card
    # background; irreversible only takes a border. See docs/design-system.md.
    "blocked_text": "#9E2A2A",
    "blocked_bg": "#F8DEDE",
    "blocked_edge": "#DD4847",
    "blocked_fill": "#B93636",
    # Informational: selection, links, the current file, plan identifiers.
    # Never used to signal risk.
    "accent_text": "#14579C",
    "accent_bg": "#E3EFFB",
    "accent_edge": "#3B8ADA",
    "accent_fill": "#1962A9",
    "accent_hover": "#1D6FBD",
    # HCL syntax. Eleven tokens rather than six: an attribute name, a function
    # call, a reference path and an interpolation delimiter are each a
    # different kind of thing, and reading HCL is mostly telling them apart.
    "syn_block": "#8A3FA8",  # resource, variable, output, module, data
    "syn_type": "#1962A9",  # provider vocabulary — "aws_instance"
    "syn_name": "#0B6B52",  # a name you chose — "api"
    "syn_attr": "#4A4740",
    "syn_string": "#8F4E0C",
    "syn_number": "#1B7383",
    "syn_fn": "#5B4BC4",
    "syn_ref": "#1962A9",
    "syn_interp": "#AC3719",
    "syn_comment": "#6E6B63",
    "syn_operator": "#54514B",
    "syn_invalid": "#9E2A2A",
    # Plan gutter. Replace is its own colour because Terraform's replace is
    # neither a create nor a destroy and it is the change people misread most.
    "plan_create": "#4C8719",
    "plan_update": "#A96C0D",
    "plan_replace": "#C4551F",
    "plan_destroy": "#B93636",
    "plan_noop": "#AEAAA1",
    "focus_ring": "#1962A9",
    # States nothing named before. Written here so no widget invents its own,
    # and as rgba so each one works over whatever surface it lands on.
    "hover": "rgba(25,24,23,0.05)",
    "pressed": "rgba(25,24,23,0.09)",
    "row_selected": "rgba(25,98,169,0.16)",
    "current_line": "rgba(25,24,23,0.035)",
    "syn_selection": "rgba(25,98,169,0.22)",
    "occurrence": "rgba(59,138,218,0.55)",
    "bracket_match": "rgba(59,138,218,0.35)",
    "map_viewport": "rgba(25,24,23,0.09)",
    "indent_guide": "rgba(25,24,23,0.10)",
}

DARK = {
    "canvas": "#131211",
    "surface": "#1A1917",
    # The buffer is the lightest surface in dark, not the darkest. A near-black
    # editor under lighter chrome inverts the figure and the ground, and #201F1D
    # is kinder over an hour than #161513.
    "panel": "#201F1D",
    "overlay": "#282725",
    "sunken": "#0E0D0C",
    "hairline": "rgba(239,237,231,0.13)",
    "hairline_strong": "rgba(239,237,231,0.24)",
    "ink": "#EFEDE7",
    "ink_muted": "#ADA99F",
    "ink_faint": "#918D84",
    "ink_ghost": "#615E57",
    "ink_on_fill": "#FFFFFF",
    "consequence_safe_text": "#B9DA8B",
    "consequence_safe_bg": "#243F10",
    "consequence_safe_edge": "#6FA436",
    "consequence_safe_fill": "#478016",
    "consequence_disruptive_text": "#F5C173",
    "consequence_disruptive_bg": "#4A2C05",
    "consequence_disruptive_edge": "#C9871A",
    "consequence_disruptive_fill": "#A0670C",
    "consequence_irreversible_text": "#F4BABA",
    "consequence_irreversible_bg": "#4E1A1A",
    "consequence_irreversible_edge": "#D9504F",
    "consequence_irreversible_fill": "#B93636",
    "consequence_irreversible_hover": "#CE3F3C",
    "blocked_text": "#F4BABA",
    "blocked_bg": "#5E1D1D",
    "blocked_edge": "#D9504F",
    "blocked_fill": "#B93636",
    "accent_text": "#9EC8F2",
    "accent_bg": "#123A62",
    "accent_edge": "#3C86D2",
    "accent_fill": "#2470BC",
    "accent_hover": "#2C7FD1",
    "syn_block": "#C99BDD",
    "syn_type": "#8CBCEC",
    "syn_name": "#67C9A5",
    "syn_attr": "#B8B4AA",
    "syn_string": "#E0A56A",
    "syn_number": "#6FC4D4",
    "syn_fn": "#A79BEE",
    "syn_ref": "#8CBCEC",
    "syn_interp": "#EE9070",
    "syn_comment": "#918D84",
    "syn_operator": "#ADA99F",
    "syn_invalid": "#F4BABA",
    "plan_create": "#8CBC52",
    "plan_update": "#DE981F",
    "plan_replace": "#E97C4C",
    "plan_destroy": "#E56E6D",
    "plan_noop": "#57544E",
    "focus_ring": "#5CA0E6",
    "hover": "rgba(255,255,255,0.07)",
    "pressed": "rgba(255,255,255,0.12)",
    "row_selected": "rgba(36,112,188,0.16)",
    "current_line": "rgba(255,255,255,0.05)",
    "syn_selection": "rgba(36,112,188,0.28)",
    "occurrence": "rgba(60,134,210,0.55)",
    "bracket_match": "rgba(60,134,210,0.35)",
    "map_viewport": "rgba(255,255,255,0.09)",
    "indent_guide": "rgba(239,237,231,0.10)",
}


def blend(top: str, bottom: str, alpha: float) -> str:
    """One colour laid over another, as an opaque hex.

    GtkSourceView's style schemes take a solid value, so a wash that is written
    as `rgba(...)` for CSS has to be flattened before the editor can use it —
    and flattening it here means the two never describe different colours.
    """

    def channels(value: str) -> tuple[int, int, int]:
        said = value.lstrip("#")
        return tuple(int(said[at : at + 2], 16) for at in (0, 2, 4))  # type: ignore[return-value]

    over, under = channels(top), channels(bottom)
    mixed = (round(a * alpha + b * (1 - alpha)) for a, b in zip(over, under, strict=True))
    return "#" + "".join(f"{part:02X}" for part in mixed)


def check_parity() -> None:
    missing_dark = set(LIGHT) - set(DARK)
    missing_light = set(DARK) - set(LIGHT)
    if missing_dark or missing_light:
        raise ValueError(
            f"token parity broken. missing in dark: {sorted(missing_dark)}, "
            f"missing in light: {sorted(missing_light)}"
        )


# ---------------------------------------------------------------------------
# Adwaita bridge
# ---------------------------------------------------------------------------
# libadwaita reads its own named colours. Repointing them means stock widgets
# (headerbar, menus, switches) inherit the palette instead of fighting it.

ADWAITA_MAP = {
    "window_bg_color": "canvas",
    "window_fg_color": "ink",
    "view_bg_color": "panel",
    "view_fg_color": "ink",
    "sidebar_bg_color": "surface",
    "sidebar_fg_color": "ink",
    "headerbar_bg_color": "surface",
    "headerbar_fg_color": "ink",
    "popover_bg_color": "overlay",
    "popover_fg_color": "ink",
    "card_bg_color": "panel",
    "card_fg_color": "ink",
    "accent_bg_color": "accent_fill",
    "accent_fg_color": "ink_on_fill",
    "accent_color": "accent_text",
    "destructive_bg_color": "consequence_irreversible_fill",
    "destructive_fg_color": "ink_on_fill",
    "destructive_color": "consequence_irreversible_text",
    "warning_bg_color": "consequence_disruptive_edge",
    "warning_color": "consequence_disruptive_text",
    "success_bg_color": "consequence_safe_edge",
    "success_color": "consequence_safe_text",
    "error_bg_color": "consequence_irreversible_fill",
    "error_color": "consequence_irreversible_text",
    # Links. Without these GTK draws its own blue-violet, which is the one
    # colour on screen that belongs to nobody's palette.
    "link_color": "accent_text",
    "visited_link_color": "accent_text",
}


def define_colors(mode: str = "light") -> str:
    palette = DARK if mode == "dark" else LIGHT
    lines = [f"/* generated from theme/tokens.py — mode: {mode}. do not edit */", ""]
    for name, value in palette.items():
        lines.append(f"@define-color tf_{name} {value};")
    lines.append("")
    lines.append("/* libadwaita bridge */")
    for adw_name, token in ADWAITA_MAP.items():
        lines.append(f"@define-color {adw_name} {palette[token]};")
    return "\n".join(lines) + "\n"


def write_sheets(directory: str = ".") -> list[str]:
    import os

    check_parity()
    written = []
    for mode in ("light", "dark"):
        path = os.path.join(directory, f"tokens.{mode}.css")
        with open(path, "w") as fh:
            fh.write(define_colors(mode))
        written.append(path)
    return written


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------


def color(name: str, mode: str | None = None):
    """Return a Gdk.RGBA for custom drawing.

    Cairo work (the plan gutter, the dependency graph) cannot read GTK named
    colours reliably across GTK 4.10+, so drawing code reads the palette here
    instead of guessing.
    """
    from gi.repository import Adw, Gdk

    if mode is None:
        mode = "dark" if Adw.StyleManager.get_default().get_dark() else "light"
    rgba = Gdk.RGBA()
    rgba.parse((DARK if mode == "dark" else LIGHT)[name])
    return rgba


def install(app=None, resource_dir: str | None = None):
    """Load the correct stylesheet and follow system light/dark changes."""
    import os

    from gi.repository import Adw, Gdk, Gtk

    base = resource_dir or os.path.dirname(os.path.abspath(__file__))
    display = Gdk.Display.get_default()
    manager = Adw.StyleManager.get_default()

    token_provider = Gtk.CssProvider()
    component_provider = Gtk.CssProvider()
    component_provider.load_from_path(os.path.join(base, "components.css"))

    def apply_mode(*_args):
        mode = "dark" if manager.get_dark() else "light"
        token_provider.load_from_string(define_colors(mode))

    apply_mode()
    manager.connect("notify::dark", apply_mode)

    # Tokens first, components second: components reference the named colours.
    Gtk.StyleContext.add_provider_for_display(
        display, token_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    Gtk.StyleContext.add_provider_for_display(
        display, component_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
    )
    return token_provider, component_provider


if __name__ == "__main__":
    import os

    here = os.path.dirname(os.path.abspath(__file__))
    for p in write_sheets(here):
        print("wrote", p)
