"""The menu is one owned specification, and this is what owns it.

Sheet 6: the reference menu this was drawn against has "Rename…" twice, "Copy
Path" twice, and both "Delete File" and "Delete", because plugins append to a
menu nobody owns. A duplicate entry should be a build failure rather than
something a user reports two years later.
"""

from __future__ import annotations

import pytest

from backsight.app.editing import OPERATIONS
from backsight.engine.layout.menus import CONTEXT_MENUS, MENU_BAR, Menu
from backsight.engine.settings.keys import DEFAULTS as KEY_DEFAULTS

# Commands the window implements directly, beyond the keymap and the line
# operations. Listed rather than discovered, so adding a menu item that resolves
# to nothing is a failure rather than a silent no-op.
TAB_ACTIONS = {
    "close-others",
    "close-left",
    "close-right",
    "close-all",
    "close-saved",
    "close-gone",
    "close-untouched",
    "keep-open",
    "pin-tab",
    "clone-into-split",
    "split-right",
    "split-down",
    "move-to-new-window",
    "compare-with",
    "diff-against-head",
    "rename-file",
    "duplicate-file",
    "move-file",
    "delete-file",
    "reveal-in-rail",
    "open-containing-folder",
    "copy-name",
    "copy-absolute-path",
    "copy-repo-path",
    "copy-module-path",
    "copy-module-source",
    "sort-tabs-manual",
    "sort-tabs-name",
    "sort-tabs-path",
    "sort-tabs-recent",
    "sort-tabs-plan-impact",
}

# Sheet 6's context menus. Each is an operation the window will implement; a
# name here is a commitment, which is why they are listed rather than
# discovered.
CONTEXT_ACTIONS = {
    "add-to-stack",
    "blame",
    "copy-resource-addresses",
    "discard-changes",
    "exclude-from-plan",
    "explain-finding",
    "file-history",
    "find-files-named",
    "find-in-folder",
    "find-references",
    "fix-finding",
    "generate-import-block",
    "new-file",
    "new-folder",
    "open-in-new-tab",
    "open-in-new-window",
    "open-policy-source",
    "open-terminal-here",
    "scaffold",
    "show-reachability",
    "show-state",
    "snippet-module",
    "snippet-output",
    "snippet-resource",
    "snippet-variable",
    "suppress-finding",
}

# Named in a menu and reaching nothing — measured against the window itself,
# not asserted. Two different problems live in here: things genuinely unbuilt
# (`blame`, `show-state`), and things that are built under another name (the
# window registers one parameterised `panel` action; the menu names
# `toggle-left-rail`). See docs/findings/007-most-of-the-menu-bar-is-not-wired.md.
#
# The test asserts this list **exactly**, so adding a dead menu item fails and
# so does wiring one without deleting its line here. It can only get shorter.
# Empty, and it stays empty. Every menu item either reaches something or says
# on the item itself why it cannot — which is a state a person can read, rather
# than a control that quietly does nothing.
NOT_WIRED: set[str] = set()

WINDOW_ACTIONS = {
    "toggle-code-lens",
    "toggle-hints",
    "open-workspace",
    "open-file",
    "save-as",
    "save-all",
    "close-window",
    "undo",
    "redo",
    "cut",
    "copy",
    "paste",
    "paste-and-indent",
    "paste-from-history",
    "select-all",
    "select-all-occurrences",
    "select-enclosing-block",
    "goto-block-start",
    "goto-block-end",
    "fold-resources",
    "toggle-status-bar",
    "full-screen",
    "toggle-gutter-verdicts",
    "toggle-inline-explanations",
    "toggle-hover-popups",
    "toggle-word-wrap",
    "toggle-rulers",
    "convert-to-lf",
    "convert-to-crlf",
    "convert-to-tabs",
    "convert-to-spaces",
    "find",
    "find-next",
    "find-previous",
    "replace",
    "goto-line",
    "goto-definition",
    "goto-matching-bracket",
    "initialise",
    "validate",
    "format-workspace",
    "convergence-run",
    "exposure-analyse",
    "run-tests-in-file",
    "extract-to-module",
    "count-to-for-each",
    "activity-log",
    "settings",
    "settings-workspace",
    "open-settings-folder",
    "key-bindings",
    "scheme-follow-system",
    "scheme-light",
    "scheme-dark",
    "about",
}


def _window_actions() -> set[str]:
    """What the running window registers. The only authority on what works."""
    gi = pytest.importorskip("gi", reason="the toolkit is not installed")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from backsight.app.window import Window

    return set(Window().list_actions())


# One list, not three. An action is known if a key is bound to it, if it is a
# line operation, if the window registers it, or if it is on the measured list
# of things that reach nothing. Keeping a separate hand-written set meant every
# wiring needed two edits and one of them was always forgotten.
KNOWN = (
    {command.action for command in KEY_DEFAULTS} | set(OPERATIONS) | _window_actions() | NOT_WIRED
)

EVERY_MENU = MENU_BAR + CONTEXT_MENUS


@pytest.fixture(params=EVERY_MENU, ids=lambda m: m.name)
def menu(request) -> Menu:
    return request.param


def test_no_two_items_a_user_sees_together_share_a_label(menu):
    """The exact defect sheet 6 names, checked where it can actually confuse.

    Per level, not flattened: `Copy path › Name` and `Sort tabs by › Name` are
    never seen side by side, and the parent says which is which.
    """
    for where, items in menu.levels():
        labels = [item.label for item in items]
        repeated = sorted({label for label in labels if labels.count(label) > 1})
        assert not repeated, f"{where} has {repeated} more than once"


def test_every_item_resolves_to_a_command_or_is_a_submenu(menu):
    for item in menu.items():
        if item.is_submenu:
            assert item.action is None, f"{item.label} is both a submenu and a command"
            continue
        if item.blocked_because and item.action is None:
            # A capability named so it is visibly absent, with the reason on it.
            continue
        if item.blocked_because:
            # A blocked item resolves to nothing on purpose — it stays visible
            # so the capability is known to exist, and it is disabled.
            continue
        assert item.action in KNOWN, f"{menu.name} → {item.label} points at {item.action}"


def test_every_section_is_named(menu):
    """A named insertion point is how a later contributor says where they belong."""
    for section in menu.sections:
        assert section.name


def test_a_blocked_item_says_why_rather_than_greying_mutely():
    """Removing it hides the capability; greying it silently reads as a bug."""
    blocked = [i for m in EVERY_MENU for i in m.items() if i.blocked_because]
    assert blocked
    for item in blocked:
        assert item.blocked_because
        assert item.shown_label.startswith(item.label)
        assert item.blocked_because in item.shown_label


def test_the_bar_has_eight_menus():
    names = [menu.name for menu in MENU_BAR]
    assert names == [
        "File",
        "Edit",
        "Selection",
        "Find",
        "Go",
        "View",
        "Git",
        "Tools",
    ]


def test_terraform_hangs_off_the_run_control_rather_than_a_bar_menu():
    """It carries the capability nobody guesses — check for drift, analyse
    public access, extract to a module. On the run control's caret it is one
    click from a button that is always visible, which is **shallower** than a
    menu bar rather than deeper, and it is the reason the application exists."""
    from backsight.engine.layout.menus import RUN_MENU

    assert RUN_MENU.name == "Terraform"
    assert RUN_MENU.sections[0].items[0].action == "plan"
    assert "Terraform" not in [menu.name for menu in MENU_BAR]


def test_no_item_appears_in_more_than_one_entry_point():
    """Three entry points and no overlap. Two places carrying the same item is
    two places a contributor can add to, and nobody can tell which is
    authoritative — which is the defect the whole specification exists against.
    """
    from collections import Counter

    from backsight.engine.layout.menus import EVERY_ENTRY_POINT

    said = Counter(
        item.action for menu in EVERY_ENTRY_POINT for item in menu.items() if item.action
    )
    assert [action for action, count in said.items() if count > 1] == []


def test_two_items_may_not_share_an_action_even_under_different_labels():
    """The guard above this one compared **labels**, so `Line wrap` and `Word
    wrap` both pointing at `toggle-word-wrap` passed it cleanly — and so did
    `Ruler` and `Rulers`. Comparing actions is what catches the pair that can
    actually confuse somebody, which is two menu items that do one thing.
    """
    from backsight.engine.layout.menus import EVERY_ENTRY_POINT

    for menu in EVERY_ENTRY_POINT:
        for where, items in menu.levels():
            actions = [item.action for item in items if item.action]
            repeated = sorted({action for action in actions if actions.count(action) > 1})
            assert not repeated, f"{where} runs {repeated} from two items"


def test_one_whitespace_toggle_rather_than_two_that_can_disagree():
    """`toggle-whitespace` wrote a setting and `toggle-show-whitespace` flipped
    the view, both were in the View menu, and they ran through different code —
    so the tick and the buffer could say different things."""
    from backsight.engine.layout.menus import EVERY_ENTRY_POINT

    actions = {item.action for menu in EVERY_ENTRY_POINT for item in menu.items() if item.action}
    assert "toggle-whitespace" in actions
    assert "toggle-show-whitespace" not in actions


def test_the_capabilities_with_no_toolkit_api_are_visible_and_named():
    """Finding 002. Absent and explained beats absent and unexplained."""
    labels = {
        item.shown_label for menu in MENU_BAR for item in menu.items() if item.blocked_because
    }
    assert any("Code folding" in label and "toolkit" in label for label in labels)
    assert any("Multiple cursors" in label and "toolkit" in label for label in labels)


def test_no_top_level_label_appears_twice_anywhere_in_the_bar():
    """One concept, one item — across the whole bar, not only within a menu.

    This caught three in the first draft of the specification, which is the
    same defect sheet 6 describes in the menu it was written against.
    """
    labels = [
        item.label for menu in MENU_BAR for section in menu.sections for item in section.items
    ]
    repeated = sorted({label for label in labels if labels.count(label) > 1})
    assert repeated == []


def test_the_tab_menu_has_one_close_rather_than_eight():
    """Sheet 8: scope and filter are two axes; the reference multiplies them out."""
    from backsight.engine.layout.menus import TAB_MENU

    top_level = [item.label for section in TAB_MENU.sections for item in section.items]
    closes = [label for label in top_level if label.startswith("Close")]
    assert closes == ["Close", "Close others", "Close…"]


def test_no_two_tab_items_differ_only_by_destroying_work():
    """The reference has "Skip Unsaved" beside "Dismiss Unsaved". One of those
    silently destroys work and its neighbour does not, and they look identical."""
    from backsight.engine.layout.menus import TAB_MENU

    labels = {item.label.lower() for item in TAB_MENU.items()}
    assert not any("unsaved" in label for label in labels)


def test_close_is_first_where_the_eye_lands():
    from backsight.engine.layout.menus import TAB_MENU

    assert TAB_MENU.sections[0].items[0].label == "Close"


def test_every_menu_action_is_actually_registered_on_the_window():
    """The stronger version of the check above.

    The list of known actions is maintained by hand, so it says a name is
    *intended* rather than that it *works*. Four annotation toggles sat in the
    View menu wired to nothing, and the hand-maintained list called them fine.

    This asks the window itself. 113 actions currently reach nothing, and that
    list is checked in: adding a dead menu item fails, and so does wiring one
    without shortening the list. It can only get smaller.
    """
    gi = pytest.importorskip("gi", reason="the toolkit is not installed")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")

    from backsight.app.window import Window

    window = Window()
    live = set(window.list_actions())

    named: set[str] = set()
    for menu in (*MENU_BAR, *CONTEXT_MENUS):
        for item in menu.items():
            if item.action and not item.blocked_because:
                named.add(item.action)

    from backsight.app.editing import OPERATIONS as LINE_OPERATIONS

    missing = sorted(named - live - set(LINE_OPERATIONS))
    added = sorted(set(missing) - NOT_WIRED)
    assert added == [], "new menu items that go nowhere: " + ", ".join(added)

    wired = sorted(NOT_WIRED - set(missing))
    assert wired == [], "wired now — take these out of NOT_WIRED: " + ", ".join(wired)
