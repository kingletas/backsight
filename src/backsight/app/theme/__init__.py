"""Colour, type and spacing, in one place.

`tokens.py` is the source of truth and is generated from nowhere — it is
written by hand and everything else reads it. `components.css` is hand-written
and contains no literal colours. Both come from the design system in
`docs/design-system.md`.

**The one idea: colour encodes consequence, not category.** Every coloured
element resolves to one of four levels — safe, disruptive, irreversible,
blocked — and `accent` is a fifth family that is explicitly not a severity.
Six severities means nobody reads any of them.

`Theme` is what the window holds. It installs the token sheet for the current
mode, reloads it when the desktop changes, and layers the components on top at
a higher priority, because the components reference the named colours.
"""

from __future__ import annotations

import weakref
from pathlib import Path
from typing import ClassVar

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")

from gi.repository import Adw, Gdk, Gtk, GtkSource

from backsight.app.theme import tokens
from backsight.engine.settings import zoom

HERE = Path(__file__).parent
SCHEMES = HERE / "schemes"
COMPONENTS = HERE / "components.css"

# The icons ship in the tree so the application has a real mark before it is
# installed anywhere. Registered here rather than in `Application`, because a
# window built any other way — a test, the smoke — was showing the broken
# image glyph.
ICONS = HERE.parents[2].parent / "data" / "icons"

LIGHT_SCHEME = "backsight-light"
DARK_SCHEME = "backsight-dark"

# What a plan action is called in the palette. The gutter keeps four colours
# because a replace is neither a create nor a destroy, and it is the change
# people misread most; the *consequence* model still files it under
# irreversible. Both are true and they answer different questions.
PLAN_TONES = {
    "add": "plan_create",
    "change": "plan_update",
    "replace": "plan_replace",
    "destroy": "plan_destroy",
    "none": "plan_noop",
    "hint": "ink_faint",
    "exposure": "consequence_irreversible_edge",
    "blocked": "blocked_edge",
}

# Consequence, which is what a person is deciding about. Four levels, and there
# is no fifth.
CONSEQUENCE = {
    "add": "safe",
    "change": "disruptive",
    "replace": "irreversible",
    "destroy": "irreversible",
    "none": "safe",
    "hint": "safe",
    "exposure": "irreversible",
    "blocked": "blocked",
}

LEVELS = ("safe", "disruptive", "irreversible", "blocked")


class Theme:
    """Installs the stylesheets and keeps them in step with the desktop.

    One per display. Two Themes on one display means two sets of providers at
    the same priority and a search path registered twice, and which stylesheet
    wins then depends on construction order — use `Theme.shared`.
    """

    _installed: ClassVar[dict[int, Theme]] = {}

    @classmethod
    def shared(cls, display: Gdk.Display | None = None) -> Theme:
        """The theme for this display, built once.

        The application builds it in `do_startup`, before any window exists, so
        stock widgets never draw once in Adwaita's grays first. A window built
        on its own — a test, the smoke — gets the same one rather than a second.
        """
        found = display or Gdk.Display.get_default()
        key = id(found)
        if key not in cls._installed:
            cls._installed[key] = cls(found)
        return cls._installed[key]

    def __init__(self, display: Gdk.Display | None = None) -> None:
        self._display = display or Gdk.Display.get_default()
        self._tokens = Gtk.CssProvider()
        self._components = Gtk.CssProvider()
        self._sizes = Gtk.CssProvider()
        self._zoom = zoom.read(tokens.TYPE["code"])
        self._manager = Adw.StyleManager.get_default()
        # What the buffer is drawn in, until settings say otherwise. Held here
        # rather than read from settings directly: the theme is per display and
        # outlives any one window.
        self._font = tokens.FONT["mono"]
        self._schemes = (LIGHT_SCHEME, DARK_SCHEME)

        if self._display is not None:
            # Tokens first, components second: the components reference the
            # named colours, so the order is not a preference.
            Gtk.StyleContext.add_provider_for_display(
                self._display, self._tokens, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
            Gtk.StyleContext.add_provider_for_display(
                self._display, self._components, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
            )
            Gtk.StyleContext.add_provider_for_display(
                self._display, self._sizes, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2
            )
        GtkSource.StyleSchemeManager.get_default().append_search_path(str(SCHEMES))
        if self._display is not None and ICONS.is_dir():
            Gtk.IconTheme.get_for_display(self._display).add_search_path(str(ICONS))
        self._manager.connect("notify::dark", lambda *_: self.apply())
        self.apply()

    @property
    def dark(self) -> bool:
        return self._manager.get_dark()

    @property
    def mode(self) -> str:
        return "dark" if self.dark else "light"

    @property
    def editor_scheme(self) -> str:
        light, dark = self._schemes
        return dark if self.dark else light

    def read_from(self, settings) -> None:
        """Takes the font and the two editor schemes from settings, and redraws."""
        wanted = str(settings.get("editor.font_family", "") or "").strip()
        # A named family with the token stack behind it, so an unavailable font
        # falls back to something monospaced rather than to the UI sans.
        self._font = f'"{wanted}", {tokens.FONT["mono"]}' if wanted else tokens.FONT["mono"]
        self._schemes = (
            str(settings.get("appearance.editor_scheme_light", LIGHT_SCHEME)),
            str(settings.get("appearance.editor_scheme_dark", DARK_SCHEME)),
        )
        self.apply()

    def apply(self) -> None:
        self._tokens.load_from_string(tokens.define_colors(self.mode))
        self._components.load_from_path(str(COMPONENTS))
        self._apply_zoom()
        for buffer in list(_buffers):
            self._set_scheme(buffer)

    @property
    def zoom(self) -> zoom.Zoom:
        return self._zoom

    def set_zoom(self, level: zoom.Zoom) -> None:
        """Resizes the buffer text and remembers it.

        The buffer only: the chrome around it is a preference somebody sets
        once, not something they reach for while reading a file.
        """
        self._zoom = level
        zoom.remember(level)
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        # A third provider, above the components, because it overrides one
        # declaration in them and nothing else.
        # A ratio, like everything else in the sheet. The zoom is a deliberate
        # choice about this buffer and the desktop's text scaling is a
        # deliberate choice about everything — somebody who has set 150% for
        # accessibility wants the code bigger too, so the two multiply.
        size = f"{tokens.ratio_of(self._zoom.size)}em"
        # **No `line-height` here.** GTK multiplies the font's natural line box
        # rather than its size, so 1.45 in a stylesheet produces a row about
        # 43% taller than the design's arithmetic. `app/leading.py` sets the row
        # in pixels, from the font actually in use, once the view exists.
        self._sizes.load_from_string(
            f".tf-buffer {{ font-size: {size}; font-family: {self._font}; }}\n"
            f".tf-buffer text {{ font-size: {size}; font-family: {self._font}; }}\n"
        )

    def prefer(self, name: str) -> None:
        """Follow the desktop, or override it. The default is to follow."""
        self._manager.set_color_scheme(preference(name))
        self.apply()

    def follow(self, buffer: GtkSource.Buffer) -> None:
        """Keeps one editor buffer on whichever scheme is current."""
        _buffers.add(buffer)
        self._set_scheme(buffer)

    def colour(self, name: str) -> Gdk.RGBA:
        """One token as an RGBA, for anything that draws rather than styles."""
        return tokens.color(name, self.mode)

    def colours(self) -> dict[str, Gdk.RGBA]:
        """Every plan tone as an RGBA, keyed by the name the app uses."""
        return {tone: self.colour(token) for tone, token in PLAN_TONES.items()}

    def _set_scheme(self, buffer: GtkSource.Buffer) -> None:
        found = GtkSource.StyleSchemeManager.get_default().get_scheme(self.editor_scheme)
        if found is not None:
            buffer.set_style_scheme(found)


# Buffers that should follow the scheme. A weak set so a closed file is not
# kept alive by the theme.
_buffers: weakref.WeakSet = weakref.WeakSet()


def preference(name: str) -> Adw.ColorScheme:
    """`follow_system`, `light` or `dark` as the style manager understands it."""
    return {
        "follow_system": Adw.ColorScheme.DEFAULT,
        "light": Adw.ColorScheme.FORCE_LIGHT,
        "dark": Adw.ColorScheme.FORCE_DARK,
    }[name]


def stylesheet(dark: bool) -> str:
    """The token sheet for one mode. Kept for anything that inspects it."""
    return tokens.define_colors("dark" if dark else "light")
