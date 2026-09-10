"""Every object on screen, and what a mouse does to it.

It comes with its own rule: **an object here with an
empty cell is a design gap rather than an intentional blank.** So the table is
declared rather than described, and the test asserts every object answers both
questions.

Right-click answers are the menu specification's, named here rather than
repeated — two lists of the same menu would disagree within a month.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Object:
    """One thing a mouse can be over, and what it does there."""

    name: str
    click: str
    menu: str
    # Anything beyond a plain click: dragging, the middle button, a double.
    also: tuple[str, ...] = field(default_factory=tuple)
    # **Where the click is actually wired**, as `module.py:symbol`. A table of
    # what a mouse does is a description until something checks it against the
    # code — and two of these described behaviour that did not exist: a plan row
    # was a box with no gesture on it, and the gutter mark had neither a click
    # nor the menu it names.
    wired: str = ""
    # A pointer and a keyboard reach the same command rather than two
    # implementations of it. Named where there is one.
    command: str = ""

    @property
    def answered(self) -> bool:
        """Both questions have an answer. An empty cell is the gap."""
        return bool(self.click.strip()) and bool(self.menu.strip())


INVENTORY: tuple[Object, ...] = (
    Object(
        "Tab",
        click="Focus the file",
        menu="Tab",
        also=(
            "Drag to reorder",
            "Drag out to split",
            "Middle-click closes",
        ),
        wired="editor.py:_on_middle_click",
    ),
    Object(
        "Gutter mark",
        click="Explain the finding on that line",
        menu="Gutter mark",
        wired="gutter_marks.py:_clicked",
        command="explain-finding",
    ),
    Object(
        "Change-map mark",
        click="Scroll to it",
        menu="Filter the map by action",
        also=("Drag the viewport", "Hover says what is there"),
        wired="change_map.py:_on_click",
    ),
    Object(
        "Plan entry",
        click="Jump to the source line",
        menu="Copy address, show the attribute diff, explain the replacement",
        wired="plan_panel.py:_row_widget",
        command="goto-resource",
    ),
    Object(
        "Verdict chip",
        click="Open whatever answers it",
        menu="Section-specific actions",
        wired="window.py:_status_segment",
        command="open-drawer",
    ),
    Object(
        "Panel divider",
        click="Drag to resize",
        menu="Reset to the default width",
        also=("Double-click collapses",),
        wired="window.py:_drawer_dragged",
    ),
    Object(
        "Rail strip",
        click="Expand the rail",
        menu="Show, hide, or choose what the rail holds",
        wired="window.py:_sidebar",
        command="toggle-left-rail",
    ),
    Object(
        "File in rail",
        click="Preview the file",
        menu="File",
        also=("Double-click opens it",),
        wired="file_tree.py:_activated",
        command="open-file",
    ),
    Object(
        "Folder in rail",
        click="Expand or collapse it",
        menu="Folder",
        also=("The whole row is the target, not the chevron",),
        wired="file_tree.py:_activated",
    ),
    Object(
        "Editor selection",
        click="Select and drag as anywhere else",
        menu="Editor",
        also=("Double-click outlines every other occurrence",),
        wired="occurrences.py:_on_mark",
    ),
    Object(
        "Command palette row",
        click="Run it",
        menu="none — the palette is one list of one kind of thing",
        wired="palette.py:choose",
        command="palette",
    ),
    Object(
        "Drawer tab",
        click="Show that tab",
        menu="none — a tab is a place, and every place is on screen",
        wired="drawer.py:_chosen",
    ),
    Object(
        "Drawer close",
        click="Close the drawer",
        menu="none — one control, one meaning",
        wired="drawer.py:close",
        command="toggle-plan-drawer",
    ),
    Object(
        "Run control",
        click="Plan; the caret opens everything the engine can do",
        menu="the caret beside it is the menu",
        wired="window.py:_run_control",
        command="plan",
    ),
    Object(
        "Workspace switcher",
        click="Open the list of workspaces",
        menu="none — the button is the list",
        wired="switcher.py",
        command="open-workspace",
    ),
    Object(
        "Console prompt",
        click="Type an expression; Return evaluates it",
        menu="the toolkit's own text menu",
        wired="console_panel.py:submit",
    ),
    Object(
        "Test run",
        click="Run the tests in that file",
        menu="Gutter mark",
        wired="run_marks.py:_on_click",
        command="run-tests-in-file",
    ),
    Object(
        "Resource block",
        # **Not folding.** GtkSourceView 5 has no folding API at all, so a fold
        # arrow was a cell describing something that could never happen. The
        # spine down the block is what says where it starts and ends, and it is
        # drawn rather than clicked.
        click="Click anywhere in it and the editor menu is scoped to it",
        menu="Editor, scoped to that resource",
        wired="window.py:_resource_under_the_caret",
    ),
)

BY_NAME = {entry.name: entry for entry in INVENTORY}

# Right-click answers that name a menu in the specification rather than
# describing one. Anything else is prose, which is fine for an object whose
# menu is not built yet.
NAMED_MENUS = {"Tab", "Gutter mark", "File", "Folder", "Editor"}


def unwired() -> list[str]:
    """Every object whose click is described and not pointed at any code.

    **A table of what a mouse does is a description until something checks it.**
    Two of these described behaviour that did not exist: a plan row was a box
    with no gesture on it, and the gutter mark had neither the click nor the
    menu it names.
    """
    return [entry.name for entry in INVENTORY if entry.click.strip() and not entry.wired.strip()]


def gaps() -> list[str]:
    """Every object that does not answer both questions."""
    return [entry.name for entry in INVENTORY if not entry.answered]
