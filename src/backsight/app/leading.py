"""Making a code row the height the design asks for.

**The design says leading, and GTK means something else by it.** On the web a
`line-height` of 1.45 multiplies the font size; GTK multiplies the font's own
natural line box, which for a monospace is already about 1.4 of its size. So
1.45 in the stylesheet produces a row about 43% taller than the design's
arithmetic, and a design stated in pixels cannot be checked against it.

So the row is set here instead, in pixels, from the font actually in use.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")

from gi.repository import GLib, Gtk, Pango


def natural_line(view: Gtk.TextView) -> int:
    """How tall one line is before anything is added to it."""
    context = view.get_pango_context()
    metrics = context.get_metrics(context.get_font_description(), None)
    return round((metrics.get_ascent() + metrics.get_descent()) / Pango.SCALE)


def wanted_row(view: Gtk.TextView, leading: float) -> int:
    """The row height the design asks for: the font's size times the leading."""
    description = view.get_pango_context().get_font_description()
    size = description.get_size() / Pango.SCALE
    if description.get_size_is_absolute():
        size = description.get_size() / Pango.SCALE
    return max(natural_line(view), round(size * leading))


def keep_the_row(view: Gtk.TextView, leading: float) -> None:
    """Sets the row now and again whenever the font underneath it changes.

    **Measuring before the view is realised measures the wrong font.** The
    stylesheet that names the family and the size is resolved at realisation,
    so a row computed in the constructor is computed against the desktop
    default and is wrong by a couple of pixels for the life of the page.
    """

    def again(*_args: object) -> bool:
        apply_leading(view, leading)
        return False

    apply_leading(view, leading)
    # Called again on a zoom, so connect once however many times this runs.
    if getattr(view, "_row_is_kept", False):
        return
    view._row_is_kept = True
    # Realisation is when the family and the size are resolved, and the idle
    # after it is when they have actually reached the Pango context.
    view.connect("realize", lambda *_: GLib.idle_add(again))
    view.connect("notify::scale-factor", again)


def apply_leading(view: Gtk.TextView, leading: float) -> int:
    """Pads the line to the design's row height, and returns what it became.

    Never negative: a row cannot be shorter than the glyphs in it, so a font
    whose natural line already exceeds the design's row keeps its own.
    """
    natural = natural_line(view)
    row = wanted_row(view, leading)
    extra = max(0, row - natural)
    view.set_pixels_above_lines(extra // 2)
    view.set_pixels_below_lines(extra - extra // 2)
    return natural + extra
