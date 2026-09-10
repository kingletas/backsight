"""Turning the menu specification into something GTK will draw.

The specification is in `engine/layout/menus.py` and is the only place a menu is
declared. This walks it. Nothing here decides what a menu contains — if it did,
there would be two owners again, which is the failure the specification exists
to prevent.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gio, Gtk

from backsight.engine.layout.menus import APP_MENU, MENU_BAR, Item, Menu, Section
from backsight.engine.settings.keys import Keymap


def _section(section: Section, keymap: Keymap) -> Gio.Menu:
    built = Gio.Menu()
    for item in section.items:
        built.append_item(_item(item, keymap))
    return built


def _item(item: Item, keymap: Keymap) -> Gio.MenuItem:
    if item.is_submenu:
        inner = Gio.Menu()
        for section in item.submenu:
            inner.append_section(None, _section(section, keymap))
        return Gio.MenuItem.new_submenu(item.label, inner)

    # A blocked item keeps its place and says why. Removing it hides the
    # capability; greying it without a reason reads as a bug.
    built = Gio.MenuItem.new(item.shown_label, None if item.blocked_because else _detailed(item))
    return built


def _detailed(item: Item) -> str | None:
    return f"win.{item.action}" if item.action else None


def model(keymap: Keymap, menus: tuple[Menu, ...] = MENU_BAR) -> Gio.Menu:
    """The whole bar."""
    bar = Gio.Menu()
    for menu in menus:
        built = Gio.Menu()
        for section in menu.sections:
            built.append_section(None, _section(section, keymap))
        bar.append_submenu(menu.name, built)
    return bar


def build(keymap: Keymap) -> Gtk.PopoverMenuBar:
    return Gtk.PopoverMenuBar.new_from_model(model(keymap))


def everything(keymap: Keymap, *, bar_shown: bool) -> Gio.Menu:
    """What `☰` carries, which depends on whether the menu bar is on.

    **No item is ever in two places.** With the bar off, the eight menus are
    submenus here and this is the only way to reach them by pointing. With the
    bar on they move to it, and `☰` keeps only what libadwaita puts in a
    primary menu — settings, keys, help and about.
    """
    built = Gio.Menu()
    if not bar_shown:
        for menu in MENU_BAR:
            inner = Gio.Menu()
            for section in menu.sections:
                inner.append_section(None, _section(section, keymap))
            built.append_submenu(menu.name, inner)
    for section in APP_MENU.sections:
        built.append_section(None, _section(section, keymap))
    return built


def primary(keymap: Keymap) -> Gtk.MenuButton:
    """The hamburger. It is the last surface there is and cannot be hidden.

    Hiding a browsable surface reveals the next one down, and this is the
    bottom of that stack — so everything stays reachable by pointing, whatever
    else has been turned off.
    """
    button = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Menu")
    button.set_menu_model(everything(keymap, bar_shown=False))
    return button
