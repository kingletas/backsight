"""Sheet 5: an empty cell in the mouse inventory is a design gap."""

from __future__ import annotations

from backsight.engine.layout.menus import CONTEXT_MENUS
from backsight.engine.layout.mouse import BY_NAME, INVENTORY, NAMED_MENUS, gaps


def test_every_object_answers_both_questions():
    """The sheet says so itself, which is why this is a test and not a table."""
    assert gaps() == []


def test_no_object_is_listed_twice():
    names = [entry.name for entry in INVENTORY]
    assert len(names) == len(set(names))


def test_every_named_menu_exists_in_the_specification():
    """A menu named here and missing there is a promise nothing keeps."""
    declared = {menu.name for menu in CONTEXT_MENUS}
    assert NAMED_MENUS <= declared


def test_the_objects_that_name_a_menu_name_a_real_one():
    for entry in INVENTORY:
        if entry.menu in NAMED_MENUS:
            assert entry.menu in {menu.name for menu in CONTEXT_MENUS}


def test_middle_click_closes_a_tab():
    """Small, expected, and its absence is noticed at once."""
    assert any("Middle-click closes" in extra for extra in BY_NAME["Tab"].also)


def test_the_change_map_can_be_read_without_navigating_away():
    """The map is only useful if a mark can be identified where it sits."""
    assert any("Hover" in extra for extra in BY_NAME["Change-map mark"].also)


def test_a_divider_can_be_collapsed_by_double_click():
    assert any("Double-click" in extra for extra in BY_NAME["Panel divider"].also)


def test_an_object_with_an_empty_cell_is_reported():
    """The rule has to fire, or it is decoration."""
    from backsight.engine.layout.mouse import Object

    assert not Object("Nothing", click="", menu="Something").answered
    assert not Object("Nothing", click="Something", menu="   ").answered


# --- the table is a claim about the code, not a description of it -----------


def test_every_click_is_pointed_at_the_code_that_does_it():
    """**A table of what a mouse does is a description until something checks
    it.** Two of these described behaviour that did not exist: a plan row was a
    box with no gesture on it, and the gutter mark had neither the click nor the
    menu it names — so five things you can do about a finding were reachable
    from no pointer at all."""
    from backsight.engine.layout.mouse import unwired

    assert unwired() == []


def test_the_code_each_one_names_is_actually_there():
    """A pointer into a module that has been renamed is a table that has gone
    back to being a description."""
    from pathlib import Path

    from backsight.engine.layout.mouse import INVENTORY

    app = Path(__file__).resolve().parents[2] / "src" / "backsight" / "app"
    missing = []
    for entry in INVENTORY:
        module, _, symbol = entry.wired.partition(":")
        where = app / module
        if not where.is_file():
            missing.append(f"{entry.name}: no {module}")
            continue
        if symbol and symbol not in where.read_text(encoding="utf-8"):
            missing.append(f"{entry.name}: {module} has no {symbol}")
    assert missing == [], missing


def test_a_pointer_and_a_keyboard_reach_the_same_command():
    """Where an object names a command, it is a real one — otherwise a mouse
    path and a key path are two implementations of one thing, and they drift."""
    from backsight.app.editing import OPERATIONS
    from backsight.engine.layout.menus import CONTEXT_MENUS, EVERY_ENTRY_POINT
    from backsight.engine.layout.mouse import INVENTORY
    from backsight.engine.settings.keys import DEFAULTS

    known = (
        {command.action for command in DEFAULTS}
        | set(OPERATIONS)
        | {
            item.action
            for menu in (*EVERY_ENTRY_POINT, *CONTEXT_MENUS)
            for item in menu.items()
            if item.action
        }
        # Two the window owns rather than the menus: opening the drawer at a
        # named section, and opening a file at a path.
        | {"open-drawer", "open-file"}
    )
    named = {entry.command for entry in INVENTORY if entry.command}
    assert named <= known, sorted(named - known)
