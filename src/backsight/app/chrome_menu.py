"""Right-click any chrome to get a panel back.

The mouse-only path. It works from the tab strip, the status bar or
the editor background, whatever is currently hidden — which is the point, since
the thing that was lost may be the thing that would have shown the way back.

The checkmarks make it the control and the answer to "what am I even looking at"
at the same time.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gio, GLib, Gtk

from backsight.engine.layout.panels import PANELS, Layout
from backsight.engine.settings.keys import Keymap


def build(layout: Layout, keymap: Keymap, implemented: set[str]) -> Gio.Menu:
    """The Show menu, listing only panels this window actually has.

    A menu offering a panel that does not exist is worse than a shorter menu.
    """
    show = Gio.Menu()
    for panel in PANELS:
        if panel.name not in implemented:
            continue
        item = Gio.MenuItem.new(panel.label, f"win.panel::{panel.name}")
        if panel.action:
            accelerator = keymap.accelerator(panel.action)
            if accelerator:
                item.set_attribute_value("accel", _string(accelerator))
        show.append_item(item)

    menu = Gio.Menu()
    menu.append_section("Show", show)

    # Always one click away, from every chrome menu. The universal escape from
    # any configuration somebody has got themselves into.
    tail = Gio.Menu()
    tail.append("Reset layout", "win.reset-layout")
    tail.append("Keyboard reference", "win.keyboard-reference")
    menu.append_section(None, tail)
    return menu


def attach(widget: Gtk.Widget, menu_for: Callable[[], Gio.Menu]) -> Gtk.GestureClick:
    """Puts a menu on one piece of chrome, built the first time it is opened.

    Nothing is built up front. A workspace has as many file rows as it has
    files and every one can carry a menu, so building a popover and a menu
    model for each of them at load would pay for menus almost none of which
    are ever opened.
    """
    held: dict[str, Gtk.PopoverMenu] = {}
    gesture = Gtk.GestureClick(button=3)

    def opened(_gesture, _n_press, x: float, y: float) -> None:
        popover = held.get("popover")
        if popover is None:
            popover = Gtk.PopoverMenu.new_from_model(menu_for())
            popover.set_parent(widget)
            popover.set_has_arrow(False)
            held["popover"] = popover
        else:
            # Rebuilt on every open so the checkmarks are current rather than
            # whatever was true the last time it was shown.
            popover.set_menu_model(menu_for())
        # Built empty and filled: a boxed struct given arguments discards them
        # and hands back a zeroed one, which opened the menu at the corner.
        where = Gdk.Rectangle()
        where.x, where.y, where.width, where.height = int(x), int(y), 1, 1
        popover.set_pointing_to(where)
        popover.popup()

    gesture.connect("pressed", opened)
    widget.add_controller(gesture)
    return gesture


def _string(value: str) -> GLib.Variant:
    return GLib.Variant.new_string(value)
