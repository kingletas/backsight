"""Every menu, as one owned specification.

The design names the failure this avoids: the reference menu it was drawn against
has "Rename…" twice, "Copy Path" twice, and both "Delete File" and "Delete" —
because plugins append to a menu nobody owns. **One declared specification with
named sections**, and `tests/architecture/test_menus.py` fails the build on a
duplicate label or an item pointing at a command that does not exist.

Two states, two treatments, and they are not the same thing:

- **Inapplicable sections vanish.** A folder that is not a root module has no
  Workspace section at all, rather than a greyed one.
- **Blocked items stay and say why.** "Apply — needs credentials" tells you the
  capability exists; removing it hides that, and greying it without a reason
  reads as a bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Item:
    """One thing a menu offers."""

    label: str
    action: str | None = None
    submenu: tuple[Section, ...] = ()
    blocked_because: str | None = None
    # Traits the object must have for this item to appear at all. "Keep open"
    # only exists on a preview tab, which is how people find out previews are
    # a thing.
    needs: tuple[str, ...] = ()

    @property
    def is_submenu(self) -> bool:
        return bool(self.submenu)

    @property
    def shown_label(self) -> str:
        """A blocked item says why on its own line, rather than greying mutely."""
        return f"{self.label} — {self.blocked_because}" if self.blocked_because else self.label


@dataclass(frozen=True)
class Section:
    """A named run of items. The name is how a later contributor says where."""

    name: str
    items: tuple[Item, ...] = field(default_factory=tuple)
    # Traits the object must have for the whole section to appear. A folder
    # that is not a root module has no Workspace section, rather than a greyed
    # one — FR-APP-24.
    needs: tuple[str, ...] = ()

    def applies(self, traits: frozenset[str]) -> bool:
        return set(self.needs) <= traits


@dataclass(frozen=True)
class Menu:
    """One menu, top-level or contextual."""

    name: str
    sections: tuple[Section, ...] = field(default_factory=tuple)

    def items(self) -> list[Item]:
        """Every item at every depth, for anything checking the whole menu."""
        found: list[Item] = []

        def walk(sections: tuple[Section, ...]) -> None:
            for section in sections:
                for item in section.items:
                    found.append(item)
                    walk(item.submenu)

        walk(self.sections)
        return found

    def given(self, *traits: str) -> Menu:
        """This menu as it appears for an object with these traits.

        Sections and items whose requirements are unmet are **removed**, not
        greyed. Greying is for something that exists and cannot be used now,
        and it always carries a reason.
        """
        held = frozenset(traits)

        def keep(sections: tuple[Section, ...]) -> tuple[Section, ...]:
            kept: list[Section] = []
            for section in sections:
                if not section.applies(held):
                    continue
                items = tuple(
                    Item(
                        label=item.label,
                        action=item.action,
                        submenu=keep(item.submenu),
                        blocked_because=item.blocked_because,
                        needs=item.needs,
                    )
                    for item in section.items
                    if set(item.needs) <= held
                )
                if items:
                    kept.append(Section(name=section.name, items=items, needs=section.needs))
            return tuple(kept)

        return Menu(name=self.name, sections=keep(self.sections))

    def levels(self) -> list[tuple[str, list[Item]]]:
        """The items a user sees together, grouped as they see them.

        Two items called `Name` are only confusable if they appear side by side.
        `Copy path › Name` and `Sort tabs by › Name` never do, because the
        parent says which is which — so uniqueness is checked per level rather
        than across the whole menu.
        """
        found: list[tuple[str, list[Item]]] = []

        def walk(sections: tuple[Section, ...], where: str) -> None:
            found.append((where, [item for section in sections for item in section.items]))
            for section in sections:
                for item in section.items:
                    if item.submenu:
                        walk(item.submenu, f"{where} › {item.label}")

        walk(self.sections, self.name)
        return found


def _s(name: str, *items: Item, needs: tuple[str, ...] = ()) -> Section:
    return Section(name=name, items=items, needs=needs)


# --- the menu bar ---------------------------------------------------------
#
# Three entry points carry every menu, and **no item appears in more than one**.
#
# | Entry | Carries |
# |---|---|
# | `☰` | the eight below as submenus, then settings, keys, help and about |
# | `Plan ▾` | everything the engine can do — the whole Terraform menu |
# | the menu bar | the same eight, flat. Off by default |
#
# Terraform is deliberately not under `☰`. It carries the capability nobody
# guesses — *Check for drift*, *Analyse public access*, *Extract to a module* —
# and on the run control's caret it is one click from a button that is always
# visible, which is **shallower** than a menu bar rather than deeper.

FILE_MENU = Menu(
    "File",
    (
        _s(
            "new",
            Item("New file", "new-file"),
            Item("New window", "new-window"),
        ),
        _s(
            "open",
            Item("Open file…", "open-file"),
            Item("Open workspace…", "open-workspace"),
            Item("Open workspace in a new window…", "open-workspace-in-new-window"),
        ),
        _s(
            "save",
            Item("Save", "save"),
            Item("Save as…", "save-as"),
            Item("Save all", "save-all"),
            Item("Revert to what is on disk", "revert-file"),
        ),
        _s("close", Item("Close tab", "close-tab"), Item("Close window", "close-window")),
    ),
)

EDIT_MENU = Menu(
    "Edit",
    (
        _s("history", Item("Undo", "undo"), Item("Redo", "redo")),
        _s(
            "clipboard",
            Item("Cut", "cut"),
            Item("Copy", "copy"),
            Item("Paste", "paste"),
            Item("Paste and indent", "paste-and-indent"),
            Item("Paste from history", "paste-from-history"),
        ),
        _s(
            "structure",
            Item(
                "Line",
                submenu=(
                    _s(
                        "line",
                        Item("Duplicate", "duplicate-lines"),
                        Item("Delete", "delete-lines"),
                        Item("Join", "join-lines"),
                    ),
                    _s(
                        "move",
                        Item("Move up", "move-lines-up"),
                        Item("Move down", "move-lines-down"),
                        Item("Swap with the line above", "swap-lines"),
                    ),
                    _s(
                        "order",
                        Item("Sort", "sort-lines"),
                        Item("Sort, case sensitive", "sort-lines-case-sensitive"),
                        Item("Reverse", "reverse-lines"),
                        Item("Remove duplicates", "unique-lines"),
                        Item("Shuffle", "shuffle-lines"),
                    ),
                ),
            ),
            Item(
                "Comment",
                submenu=(
                    _s(
                        "comment",
                        Item("Toggle line comment", "toggle-line-comment"),
                        Item("Toggle block comment", "toggle-block-comment"),
                    ),
                ),
            ),
            # HTML tag operations make no sense here; HCL block operations are
            # the equivalent need.
            Item(
                "Block",
                submenu=(
                    _s(
                        "blocks",
                        Item("Go to the start of the block", "goto-block-start"),
                        Item("Go to the end of the block", "goto-block-end"),
                        # GtkSourceView 5 exposes no folding at all — not a
                        # partial API, none. See docs/findings/002.
                        Item(
                            "Fold all resources",
                            "fold-resources",
                            blocked_because="this toolkit has no code folding",
                        ),
                    ),
                ),
            ),
        ),
        _s(
            "shape",
            Item("Format document", "format-document"),
            Item(
                "Convert indentation",
                submenu=(
                    _s(
                        "indentation",
                        Item("To tabs", "convert-to-tabs"),
                        Item("To spaces", "convert-to-spaces"),
                    ),
                ),
            ),
            Item(
                "Convert line endings",
                submenu=(
                    _s(
                        "endings",
                        Item("To LF", "convert-to-lf"),
                        Item("To CRLF", "convert-to-crlf"),
                    ),
                ),
            ),
        ),
        _s(
            "unavailable",
            Item("Code folding", blocked_because="not available in this toolkit"),
        ),
    ),
)

SELECTION_MENU = Menu(
    "Selection",
    (
        _s(
            "select",
            Item("Select all", "select-all"),
            Item("Expand the selection to the enclosing block", "select-enclosing-block"),
        ),
        _s(
            "occurrences",
            Item("Select the next occurrence", "select-next-occurrence"),
            Item("Select all occurrences", "select-all-occurrences"),
        ),
        # Named so the absence is visible and explained, with what to use
        # instead on the item itself. A dead key that says nothing is the worst
        # moment this application has.
        _s(
            "unavailable",
            Item(
                "Multiple cursors",
                blocked_because=(
                    "no API in this toolkit — Select all occurrences is the nearest thing"
                ),
            ),
            Item("Column selection", blocked_because="no API in this toolkit"),
        ),
    ),
)

FIND_MENU = Menu(
    "Find",
    (
        _s(
            "find",
            Item("Find…", "find"),
            Item("Find next", "find-next"),
            Item("Find previous", "find-previous"),
            Item("Replace…", "replace"),
        ),
        _s(
            "workspace",
            Item("Find in this folder…", "find-in-folder"),
            Item("Find files by name…", "find-files-named"),
        ),
    ),
)

GO_MENU = Menu(
    "Go",
    (
        _s(
            "goto",
            Item("Go to anything…", "goto-file"),
            Item("Go to resource…", "goto-resource"),
            Item("Go to line…", "goto-line"),
            Item("Go to problem…", "goto-problem"),
        ),
        _s(
            "code",
            Item("Go to definition", "goto-definition"),
            Item("Find references", "find-references"),
            Item("Go to the matching brace", "goto-matching-bracket"),
        ),
        # Navigation history, which did not exist anywhere in the application.
        _s(
            "history",
            Item("Back", "go-back"),
            Item("Forward", "go-forward"),
            Item("Switch file", "switch-file"),
        ),
    ),
)

VIEW_MENU = Menu(
    "View",
    (
        _s(
            "panels",
            Item("Rail", "toggle-left-rail"),
            Item("Drawer", "toggle-plan-drawer"),
            Item("Change map", "toggle-change-map"),
            Item("Verdict line", "toggle-status-bar"),
            Item("Menu bar", "toggle-menu-bar"),
            Item("Console", "toggle-console"),
        ),
        # A preset is not a mode: toggling any single panel leaves it behind and
        # the application stops claiming to be in one. There is no state to get
        # stuck in and nothing to escape from.
        _s(
            "layout",
            Item(
                "Layout",
                submenu=(
                    _s(
                        "presets",
                        Item("Focus", "layout-focus"),
                        Item("Work", "layout-work"),
                        Item("Review", "layout-review"),
                    ),
                    _s(
                        "window",
                        Item("Reset the layout", "reset-layout"),
                        Item("Full screen", "full-screen"),
                        Item("Distraction free", "toggle-distraction-free"),
                    ),
                ),
            ),
            Item(
                "Split",
                submenu=(
                    _s(
                        "split",
                        Item("Right", "split-right"),
                        Item("Down", "split-down"),
                        Item("Back to one pane", "unsplit"),
                    ),
                ),
            ),
            Item(
                "Peek",
                submenu=(
                    _s(
                        "peek",
                        Item("At the rail", "peek-rail"),
                        Item("At the drawer", "peek-drawer"),
                        Item("Keep what you are looking at", "keep-peeked"),
                    ),
                ),
            ),
        ),
        # One of each. There were two Word wraps, two Rulers, and two
        # Whitespaces running through different code — so the tick and the
        # buffer could disagree about what was on.
        _s(
            "editor-view",
            Item("Line numbers", "toggle-line-numbers"),
            Item("Word wrap", "toggle-word-wrap"),
            Item("Rulers", "toggle-rulers"),
            Item("Whitespace", "toggle-whitespace"),
            Item("Indent guide", blocked_because="no API in this toolkit"),
        ),
        _s(
            "annotations",
            Item("Gutter marks", "toggle-gutter-verdicts"),
            Item("Inline explanations", "toggle-inline-explanations"),
            Item("Code lens", "toggle-code-lens"),
            Item("Resolved values", "toggle-hints"),
            Item("Hover popups", "toggle-hover-popups"),
        ),
        _s(
            "size",
            Item("Larger text", "zoom-in"),
            Item("Smaller text", "zoom-out"),
            Item("Normal text size", "zoom-reset"),
        ),
    ),
)

GIT_MENU = Menu(
    "Git",
    (
        _s("working", Item("Changes, staging and commit", "git")),
        _s(
            "branches",
            Item("New branch…", "new-branch"),
            Item("Switch branch…", "switch-branch"),
            Item("Push…", "push"),
        ),
        _s(
            "file",
            Item("Diff this file against HEAD", "diff-against-head"),
            Item("History of this file…", "file-history"),
            Item("Blame…", "blame"),
            Item("Discard the changes to this file…", "discard-changes"),
        ),
        _s("remote", Item("Clone a repository…", "clone")),
    ),
)

TOOLS_MENU = Menu(
    "Tools",
    (
        _s(
            "commands",
            # The product's real interface, and it was in no menu at all.
            Item("Command palette…", "palette"),
            Item("Evaluate an expression…", "explain-engine"),
        ),
        # Everything Backsight ran, with arguments, timing and exit status. When
        # the engine does something unexpected the first question is always what
        # was actually run.
        _s(
            "logs",
            Item("Activity log", "activity-log"),
            Item("History of plans and applies", "history"),
            Item("What the last apply printed", "apply-logs"),
        ),
        _s(
            "here",
            Item("Open a terminal here", "open-terminal-here"),
            Item("Reveal the workspace in Files", "open-containing-folder"),
        ),
    ),
)

# --- the run control ------------------------------------------------------
#
# The whole Terraform menu, hanging off the button that runs the first item in
# it. Nine sections and twenty-five items in one flat list was a dumping
# ground; refactoring, the library and documentation are three submenus now,
# and running, checking and analysing are three flat groups.

RUN_MENU = Menu(
    "Terraform",
    (
        _s(
            "run",
            Item("Plan", "plan"),
            Item("Apply…", "apply"),
            Item("Cancel the run", "cancel-run"),
        ),
        _s(
            "prepare",
            Item("Initialise", "initialise"),
            Item("Validate", "validate"),
            Item("Check formatting", "format-workspace"),
        ),
        _s(
            "analysis",
            Item("Check for drift", "check-drift"),
            Item("Analyse public access", "exposure-analyse"),
            Item("What this plan costs", "show-cost"),
            Item("Check policies", "policy-scan"),
            Item("Policy findings", "policy-findings"),
            Item("Convergence: run", "convergence-run"),
        ),
        _s(
            "tests",
            Item("Run all tests", "run-tests"),
            Item("Run the tests in this file", "run-tests-in-file"),
        ),
        _s(
            "work",
            Item(
                "Refactor",
                submenu=(
                    _s(
                        "refactor",
                        Item("Rename resource…", "rename-resource"),
                        Item("Extract to a module…", "extract-to-module"),
                        Item("Convert count to for_each…", "count-to-for-each"),
                        # The id an import block needs is per resource type — an
                        # ARN for one, a name for another, a compound key for a
                        # third — and the provider schema does not carry it.
                        Item(
                            "Generate an import block",
                            "generate-import-block",
                            blocked_because="the import id format is not in the provider schema",
                        ),
                    ),
                ),
            ),
            Item(
                "Library",
                submenu=(
                    _s(
                        "library",
                        Item("Open the library…", "library"),
                        Item("Library for this resource", "library-for-resource"),
                        Item("Save the selection to the library…", "save-to-library"),
                    ),
                ),
            ),
            Item(
                "Documentation",
                submenu=(
                    _s(
                        "documentation",
                        Item("Documentation for this resource", "docs-for-resource"),
                        Item("Provider documentation…", "documentation"),
                        Item("What is mirrored on this machine", "mirrored-docs"),
                    ),
                ),
            ),
        ),
        _s(
            "estate",
            Item("Stacks…", "stacks"),
            Item("Show the state…", "show-state"),
            Item("What this machine can authenticate as", "credentials"),
        ),
    ),
)

# --- the primary menu -----------------------------------------------------
#
# What libadwaita puts in a primary menu, and nothing that belongs in a bar
# menu. With the menu bar off the eight above are prepended to this as
# submenus; with it on they move to the bar and this keeps only what is here.

APP_MENU = Menu(
    "Backsight",
    (
        _s(
            "settings",
            Item("Settings…", "settings"),
            Item("Settings — this workspace", "settings-workspace"),
            Item("Key bindings…", "key-bindings"),
        ),
        _s(
            "appearance",
            Item(
                "Colour scheme",
                submenu=(
                    _s(
                        "scheme",
                        Item("Follow the system", "scheme-follow-system"),
                        Item("Light", "scheme-light"),
                        Item("Dark", "scheme-dark"),
                    ),
                ),
            ),
            Item("Editor font…", "editor-font"),
            Item("Open the settings folder…", "open-settings-folder"),
        ),
        _s(
            "help",
            Item("Keyboard reference", "keyboard-reference"),
            # Products almost never write this page. This one has already
            # written the reasoning, in docs/findings/.
            Item("What Backsight will not do", "limits"),
            Item("Release notes", "release-notes"),
            Item("Report a problem…", "report-a-problem"),
        ),
        _s("about", Item("About Backsight", "about")),
    ),
)

# --- context menus --------------------------------------------------------

# Nine items at the top level and two submenus, where the reference
# menu has thirty — because scope and filter are two axes and it multiplies
# them out. "Close" goes back at the top, where the eye lands first.
TAB_MENU = Menu(
    "Tab",
    (
        _s(
            "close",
            Item("Close", "close-tab"),
            Item("Close others", "close-others"),
            Item(
                "Close…",
                submenu=(
                    _s(
                        "scope",
                        Item("To the left", "close-left"),
                        Item("To the right", "close-right"),
                        Item("All", "close-all"),
                    ),
                    _s(
                        "filter",
                        Item("Saved only", "close-saved"),
                        Item("Files gone from disk", "close-gone"),
                        # Its version of "close unmodified", for infrastructure.
                        Item("Not touched by the plan", "close-untouched"),
                    ),
                ),
            ),
            Item("Reopen last closed", "reopen-tab"),
        ),
        _s(
            "arrange",
            # Only appears on a preview tab, which is how people learn preview
            # tabs exist at all.
            Item("Keep open", "keep-open", needs=("preview",)),
            Item("Pin", "pin-tab"),
            Item("Clone into split", "clone-into-split"),
            Item("Split right", "split-right"),
            Item("Split down", "split-down"),
            Item("Back to one pane", "unsplit"),
            Item("Move to new window", "move-to-new-window"),
        ),
        _s(
            "save",
            Item("Save", "save"),
            Item("Save as…", "save-as"),
            Item("Save all", "save-all"),
            Item("Compare with…", "compare-with"),
            Item("Diff against HEAD", "diff-against-head"),
        ),
        _s(
            "file",
            Item("Rename…", "rename-file"),
            Item("Duplicate…", "duplicate-file"),
            Item("Move to…", "move-file"),
            Item("Delete file…", "delete-file"),
        ),
        _s(
            "locate",
            Item("Reveal in rail", "reveal-in-rail"),
            Item("Open containing folder…", "open-containing-folder"),
            Item(
                "Copy path",
                submenu=(
                    _s(
                        "copy",
                        Item("Name", "copy-name"),
                        Item("Absolute", "copy-absolute-path"),
                        Item("Relative to repository", "copy-repo-path"),
                        Item("Relative to module", "copy-module-path"),
                        Item("As a module source", "copy-module-source"),
                    ),
                ),
            ),
            Item(
                "Sort tabs by",
                submenu=(
                    _s(
                        "sort",
                        Item("Manual", "sort-tabs-manual"),
                        Item("Name", "sort-tabs-name"),
                        Item("Path", "sort-tabs-path"),
                        Item("Recently used", "sort-tabs-recent"),
                        Item("Plan impact", "sort-tabs-plan-impact"),
                    ),
                ),
            ),
        ),
    ),
)

# Terraform actions come first: the reason someone opened
# this application goes at the top, and the file operations every editor has
# sit below.
FILE_CONTEXT_MENU = Menu(
    "File",
    (
        _s(
            "terraform",
            Item("Plan this workspace", "plan"),
            Item("Format document", "format-document"),
            Item("Validate", "validate"),
            Item("Copy resource addresses", "copy-resource-addresses"),
            needs=("terraform",),
        ),
        _s(
            "open",
            Item("Open", "open-file"),
            Item("Open in new tab", "open-in-new-tab"),
            Item(
                "Open in split",
                submenu=(
                    _s(
                        "direction",
                        Item("Right", "split-right"),
                        Item("Down", "split-down"),
                    ),
                ),
            ),
            Item("Open in new window", "open-in-new-window"),
        ),
        _s(
            "file",
            Item("Rename…", "rename-file"),
            Item("Duplicate…", "duplicate-file"),
            Item("Move to…", "move-file"),
            Item("Delete…", "delete-file"),
        ),
        _s(
            "clipboard",
            Item("Copy", "copy"),
            Item("Copy name", "copy-name"),
            Item("Copy path", "copy-absolute-path"),
            Item("Copy relative path", "copy-repo-path"),
        ),
        _s(
            "git",
            Item("Diff against HEAD", "diff-against-head"),
            Item("File history…", "file-history"),
            Item("Blame…", "blame"),
            Item("Discard changes…", "discard-changes"),
            needs=("tracked",),
        ),
        _s(
            "locate",
            Item("Reveal in Files", "open-containing-folder"),
            # A plan covers a module, not a file. Excluding one would mean a
            # `-target` per resource declared in it, which produces a partial
            # plan — and showing a partial plan as though it were the plan is
            # exactly the confident-but-wrong claim this product exists against.
            Item(
                "Exclude from plan",
                "exclude-from-plan",
                needs=("terraform",),
                blocked_because="a plan covers a module, not a file",
            ),
        ),
    ),
)

# A root module is a stack candidate, and the folder menu is where a user will
# look for that. The Workspace section is absent entirely on a folder that is
# not a root module — not greyed.
FOLDER_CONTEXT_MENU = Menu(
    "Folder",
    (
        _s(
            "workspace",
            Item("Plan", "plan"),
            Item("Initialise", "initialise"),
            Item("Convergence: run", "convergence-run"),
            Item("Show state…", "show-state"),
            Item("Add to stack definition…", "add-to-stack", blocked_because="not built yet"),
            needs=("root_module",),
        ),
        _s(
            "create",
            Item("New file…", "new-file"),
            Item("New folder…", "new-folder"),
            Item("Scaffold from catalog…", "scaffold", blocked_because="not built yet"),
        ),
        _s(
            "find",
            Item("Find in folder…", "find-in-folder"),
            Item("Find files named…", "find-files-named"),
        ),
        _s(
            "folder",
            Item("Rename…", "rename-file"),
            Item("Move to…", "move-file"),
            Item("Delete…", "delete-file"),
        ),
        _s(
            "locate",
            Item("Copy path", "copy-absolute-path"),
            Item("Open in new window", "open-in-new-window"),
            Item("Open containing folder…", "open-containing-folder"),
            Item("Open terminal here", "open-terminal-here"),
        ),
    ),
)

# The menu on a gutter mark. Every item is about the one finding under the
# cursor, so there is no scope to get wrong.
GUTTER_MENU = Menu(
    "Gutter mark",
    (
        _s(
            "finding",
            Item("Explain this finding", "explain-finding"),
            Item("Show reachability path", "show-reachability"),
            Item("Suppress with expiry…", "suppress-finding"),
            Item("Open policy source", "open-policy-source", needs=("policy",)),
            Item("Fix automatically", "fix-finding", blocked_because="no fix available"),
        ),
    ),
)

# The menu on the editor surface itself.
EDITOR_MENU = Menu(
    "Editor",
    (
        _s(
            "refactor",
            Item("Rename resource…", "rename-resource"),
            Item("Extract to module…", "extract-to-module"),
            Item("Convert count to for_each…", "count-to-for-each"),
            # The id an import block needs is per resource type — an ARN for
            # one, a name for another, a compound key for a third — and the
            # provider schema does not carry it. Writing a block with a guessed
            # id would produce a file that fails at apply.
            Item(
                "Generate import block…",
                "generate-import-block",
                blocked_because="the import id format is not in the provider schema",
            ),
            needs=("terraform",),
        ),
        _s(
            "navigate",
            Item("Go to definition", "goto-definition"),
            Item("Find references", "find-references"),
            Item("Go to resource…", "goto-resource"),
            needs=("terraform",),
        ),
        _s(
            "reference",
            Item("Provider documentation", "provider-docs"),
            Item("Scaffold from catalog…", "scaffold", blocked_because="not built yet"),
            Item(
                "Insert snippet",
                submenu=(
                    _s(
                        "snippets",
                        Item("Resource", "snippet-resource"),
                        Item("Variable", "snippet-variable"),
                        Item("Output", "snippet-output"),
                        Item("Module call", "snippet-module"),
                    ),
                ),
            ),
            needs=("terraform",),
        ),
        _s(
            "clipboard",
            Item("Cut", "cut"),
            Item("Copy", "copy"),
            Item("Paste", "paste", blocked_because="clipboard empty"),
        ),
        _s(
            "run",
            Item("Plan this workspace", "plan"),
            Item("Apply", "apply"),
            needs=("terraform",),
        ),
    ),
)

CONTEXT_MENUS: tuple[Menu, ...] = (
    FILE_CONTEXT_MENU,
    FOLDER_CONTEXT_MENU,
    TAB_MENU,
    GUTTER_MENU,
    EDITOR_MENU,
)

MENU_BAR: tuple[Menu, ...] = (
    FILE_MENU,
    EDIT_MENU,
    SELECTION_MENU,
    FIND_MENU,
    GO_MENU,
    VIEW_MENU,
    GIT_MENU,
    TOOLS_MENU,
)

# Everything a user can reach by pointing, for anything checking that no item
# is in two places at once.
EVERY_ENTRY_POINT: tuple[Menu, ...] = (*MENU_BAR, RUN_MENU, APP_MENU)
