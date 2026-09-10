"""Turning the owned menu specification into something the toolkit can show.

The specification decides what a menu contains; this decides nothing
and only translates. Anything that looks like a decision here — an item added,
a section reordered, a label reworded — belongs in `engine/layout/menus.py`
instead, or the specification stops being the thing that owns the menus.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, GLib

from backsight.engine.layout.menus import Item, Menu, Section
from backsight.engine.settings.keys import Keymap

# What a blocked item points at. It stays in the menu and stays disabled, so
# the capability is visible and the reason is readable.
NOTHING = "win.nothing"


def to_model(menu: Menu, keymap: Keymap | None = None) -> Gio.Menu:
    """One menu specification as a `Gio.Menu`, sections and all."""
    model = Gio.Menu()
    for section in menu.sections:
        model.append_section(None, _section(section, keymap))
    return model


def _section(section: Section, keymap: Keymap | None) -> Gio.Menu:
    model = Gio.Menu()
    for item in section.items:
        if item.is_submenu:
            model.append_submenu(item.label, _submenu(item, keymap))
            continue
        model.append_item(_item(item, keymap))
    return model


def _submenu(item: Item, keymap: Keymap | None) -> Gio.Menu:
    model = Gio.Menu()
    for section in item.submenu:
        model.append_section(None, _section(section, keymap))
    return model


def _item(item: Item, keymap: Keymap | None) -> Gio.MenuItem:
    entry = Gio.MenuItem.new(item.shown_label, _target(item))
    if keymap is not None and item.action:
        accelerator = keymap.accelerator(item.action)
        if accelerator:
            entry.set_attribute_value("accel", GLib.Variant.new_string(accelerator))
    return entry


def _target(item: Item) -> str:
    """A blocked item is pointed at an action nobody enables, so it greys out.

    Removing it instead would hide that the capability exists, which is the
    opposite of what a blocked item is for.
    """
    if item.blocked_because or not item.action:
        return NOTHING
    return f"win.{item.action}"
