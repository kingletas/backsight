"""Sheet 6: inapplicable sections vanish, blocked items stay and say why."""

from __future__ import annotations

from backsight.engine.layout.menus import (
    CONTEXT_MENUS,
    EDITOR_MENU,
    FILE_CONTEXT_MENU,
    FOLDER_CONTEXT_MENU,
    GUTTER_MENU,
    TAB_MENU,
)


def sections(menu) -> list[str]:
    return [section.name for section in menu.sections]


def labels(menu) -> list[str]:
    return [item.label for section in menu.sections for item in section.items]


def test_all_four_objects_have_a_menu():
    assert set(CONTEXT_MENUS) == {
        FILE_CONTEXT_MENU,
        FOLDER_CONTEXT_MENU,
        TAB_MENU,
        GUTTER_MENU,
        EDITOR_MENU,
    }


def test_a_folder_that_is_not_a_root_module_has_no_workspace_section():
    """Absent entirely, not greyed. Two states, two treatments — FR-APP-24."""
    ordinary = FOLDER_CONTEXT_MENU.given()
    assert "workspace" not in sections(ordinary)
    assert "Plan" not in labels(ordinary)


def test_a_root_module_folder_offers_the_workspace_section_first():
    root = FOLDER_CONTEXT_MENU.given("root_module")
    assert sections(root)[0] == "workspace"
    assert labels(root)[0] == "Plan"


def test_terraform_actions_come_before_the_file_operations():
    """The reason someone opened this application goes at the top."""
    tf = FILE_CONTEXT_MENU.given("terraform", "tracked")
    assert sections(tf)[0] == "terraform"
    assert labels(tf)[0] == "Plan this workspace"


def test_a_readme_has_no_terraform_section_at_all():
    readme = FILE_CONTEXT_MENU.given("tracked")
    assert "terraform" not in sections(readme)
    assert "Exclude from plan" not in labels(readme)


def test_an_untracked_file_has_no_git_section():
    untracked = FILE_CONTEXT_MENU.given("terraform")
    assert "git" not in sections(untracked)


def test_keep_open_appears_only_on_a_preview_tab():
    """It is how people discover preview tabs exist."""
    assert "Keep open" in labels(TAB_MENU.given("preview"))
    assert "Keep open" not in labels(TAB_MENU.given())


def test_a_blocked_item_stays_and_carries_its_reason():
    """Removing it would hide that the capability exists at all."""
    editor = EDITOR_MENU.given("terraform")
    paste = next(
        item for section in editor.sections for item in section.items if item.label == "Paste"
    )
    assert paste.blocked_because == "clipboard empty"
    assert paste.shown_label == "Paste — clipboard empty"


def test_a_finding_with_no_policy_source_hides_that_item():
    assert "Open policy source" not in labels(GUTTER_MENU.given())
    assert "Open policy source" in labels(GUTTER_MENU.given("policy"))


def test_a_section_left_with_no_items_disappears_with_them():
    """An empty heading is worse than no heading."""
    assert "finding" in sections(GUTTER_MENU.given())
    empty = TAB_MENU.given()
    assert all(section.items for section in empty.sections)


def test_filtering_never_invents_an_item():
    """Whatever `given` returns is a subset of the specification."""
    for menu in CONTEXT_MENUS:
        every = {item.label for item in menu.items()}
        for traits in ((), ("terraform",), ("root_module", "terraform", "tracked", "preview")):
            assert {item.label for item in menu.given(*traits).items()} <= every
