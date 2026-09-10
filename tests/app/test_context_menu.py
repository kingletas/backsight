"""The translation adds nothing the specification did not say."""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")

from backsight.app.context_menu import NOTHING, to_model  # noqa: E402
from backsight.engine.layout.menus import (  # noqa: E402
    CONTEXT_MENUS,
    EDITOR_MENU,
    FOLDER_CONTEXT_MENU,
    TAB_MENU,
)
from backsight.engine.settings.keys import Keymap  # noqa: E402


def entries(model) -> list[tuple[str, str | None]]:
    """Every label and target in a model, sections and submenus flattened."""
    from gi.repository import Gio

    found: list[tuple[str, str | None]] = []
    for index in range(model.get_n_items()):
        label = model.get_item_attribute_value(index, "label")
        target = model.get_item_attribute_value(index, "action")
        if label is not None:
            found.append((label.get_string(), target.get_string() if target else None))
        for link in ("section", "submenu"):
            child = model.get_item_link(index, link)
            if isinstance(child, Gio.Menu):
                found.extend(entries(child))
    return found


def test_every_item_in_the_specification_reaches_the_model():
    for menu in CONTEXT_MENUS:
        spec = {item.shown_label for item in menu.items()}
        assert spec <= {label for label, _ in entries(to_model(menu))}


def test_the_translation_invents_nothing():
    for menu in CONTEXT_MENUS:
        spec = {item.shown_label for item in menu.items()}
        assert {label for label, _ in entries(to_model(menu))} <= spec


def test_a_blocked_item_stays_and_points_at_nothing():
    """It greys out with its reason readable, rather than disappearing."""
    found = dict(entries(to_model(EDITOR_MENU.given("terraform"))))
    assert found["Paste — clipboard empty"] == NOTHING


def test_a_working_item_points_at_a_window_action():
    found = dict(entries(to_model(TAB_MENU)))
    assert found["Close"] == "win.close-tab"


def test_a_filtered_menu_translates_only_what_survived():
    ordinary = to_model(FOLDER_CONTEXT_MENU.given())
    assert "Plan" not in [label for label, _ in entries(ordinary)]


def test_an_accelerator_is_carried_through_when_the_keymap_has_one():
    model = to_model(TAB_MENU, Keymap.build())
    from gi.repository import Gio

    def accel(model, wanted: str) -> str | None:
        for index in range(model.get_n_items()):
            label = model.get_item_attribute_value(index, "label")
            if label is not None and label.get_string() == wanted:
                value = model.get_item_attribute_value(index, "accel")
                return value.get_string() if value else None
            for link in ("section", "submenu"):
                child = model.get_item_link(index, link)
                if isinstance(child, Gio.Menu):
                    found = accel(child, wanted)
                    if found:
                        return found
        return None

    assert accel(model, "Close") == "<Control>w"
