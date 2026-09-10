"""What every key does, as data rather than as code.

`⌘` in the design sheets is the primary modifier, and on Linux that is Ctrl.
Super belongs to the desktop shell — a stock GNOME already owns `Super+P`,
`Super+D`, `Super+S` and `Super+M`, which are go-to-file, the plan drawer, save
and the menu bar. Binding those would ship four dead keys.

Every binding is editable. Two are not unbindable: the floor says the
command palette and the keyboard reference are what everything else rests on, so
removing them is how a person gets trapped.

**Conflicts are reported, never resolved by load order.** FR-APP-27. A
keymap that silently drops one of two bindings is one where the answer to "why
doesn't my key work" is invisible.
"""

from __future__ import annotations

from dataclasses import dataclass

# Removing either of these is refused. Everything else in the application is
# reachable from one of them.
THE_FLOOR = ("palette", "keyboard-reference")


@dataclass(frozen=True)
class Command:
    """One thing a person can ask for, and what it is called."""

    action: str
    label: str
    section: str
    accelerator: str | None = None

    @property
    def is_floor(self) -> bool:
        return self.action in THE_FLOOR


# The default keymap. Written once here; the settings file overrides it.
DEFAULTS: tuple[Command, ...] = (
    # Panels — the table that is also the restore path.
    Command("toggle-left-rail", "Left rail", "Panels", "<Control>b"),
    # `Ctrl+D` belongs to selecting the next occurrence, which is the key
    # people press without thinking about it. The drawer takes the one every
    # editor with a bottom panel uses.
    Command("toggle-plan-drawer", "Drawer", "Panels", "<Control>j"),
    Command("toggle-console", "Console", "Panels", "<Control>grave"),
    # Beside the rail's own key, because they are the same kind of decision.
    # `Ctrl+Shift+M` belongs to expanding a selection to its block.
    Command("toggle-menu-bar", "Menu bar", "Panels", "<Control><Shift>b"),
    Command("reset-layout", "Reset layout", "Panels", "<Control>k"),
    # Navigation — the palette prefixes.
    Command("palette", "Command palette", "Navigate", "<Control><Shift>p"),
    Command("goto-file", "Go to file", "Navigate", "<Control>p"),
    Command("goto-resource", "Go to resource", "Navigate", "<Control>r"),
    Command("provider-docs", "Provider documentation", "Navigate", "<Control>numbersign"),
    # Ctrl+? for the reference, so Ctrl+/ can be the comment toggle every
    # editor binds it to.
    Command("keyboard-reference", "Keyboard reference", "Navigate", "<Control>question"),
    Command("goto-line", "Go to line", "Navigate", "<Control>l"),
    # The whole point is that it beats typing the block again, so it is one key.
    Command("library", "Library", "Navigate", "<Control>e"),
    Command("save-to-library", "Save selection to library", "Navigate", "<Control><Shift>e"),
    # Terraform.
    Command("plan", "Plan", "Terraform", "<Control>Return"),
    # **Apply has no shortcut, deliberately.** It is the one irreversible
    # thing in the product, and a key that reaches it from anywhere makes it
    # the easiest thing to do by accident. It lives at the end of the review
    # that justifies it.
    Command("apply", "Apply", "Terraform", None),
    Command("run-tests", "Run tests", "Terraform", "<Control>t"),
    Command("rename-resource", "Rename resource", "Terraform", "F2"),
    # The editor's own size. The most commonly missed shortcut in an editor
    # and the most commonly noticed.
    Command("zoom-in", "Larger text", "View", "<Control>equal"),
    Command("zoom-out", "Smaller text", "View", "<Control>minus"),
    Command("zoom-reset", "Normal text size", "View", "<Control>0"),
    # Find. The requirements name each of these and none of them was bound.
    Command("find", "Find", "Find", "<Control>f"),
    Command("replace", "Find and replace", "Find", "<Control>h"),
    Command("find-next", "Find next", "Find", "<Control>g"),
    Command("find-previous", "Find previous", "Find", "<Control><Shift>g"),
    Command("find-in-folder", "Find in workspace", "Find", "<Control><Shift>f"),
    # Editing.
    Command("undo", "Undo", "Edit", "<Control>z"),
    Command("redo", "Redo", "Edit", "<Control><Shift>z"),
    Command("select-all", "Select all", "Edit", "<Control>a"),
    Command("toggle-line-comment", "Toggle comment", "Edit", "<Control>slash"),
    Command("duplicate-lines", "Duplicate line", "Edit", "<Control><Shift>d"),
    Command("move-lines-up", "Move line up", "Edit", "<Alt>Up"),
    Command("move-lines-down", "Move line down", "Edit", "<Alt>Down"),
    Command("toggle-line-numbers", "Line numbers", "View", None),
    Command("toggle-word-wrap", "Line wrap", "View", "<Alt>z"),
    Command("toggle-whitespace", "Whitespace", "View", None),
    Command("toggle-rulers", "Ruler", "View", None),
    Command("toggle-distraction-free", "Distraction free", "View", "<Control><Shift>Return"),
    Command("format-document", "Format document", "Terraform", "<Control><Shift>i"),
    Command("format-workspace", "Check formatting", "Terraform", None),
    # Files. The everyday ones every editor binds, and whose absence reads as
    # "shortcuts do not work" rather than as a missing feature — the workspace
    # switcher was already *showing* Ctrl+O with nothing behind it.
    Command("open-workspace", "Open workspace…", "File", "<Control>o"),
    Command("open-file", "Open file…", "File", "<Control><Shift>o"),
    Command("new-file", "New file", "File", "<Control>n"),
    Command("save", "Save", "File", "<Control>s"),
    Command("save-as", "Save as…", "File", "<Control><Shift>s"),
    Command("save-all", "Save all", "File", "<Control><Alt>s"),
    Command("close-tab", "Close tab", "File", "<Control>w"),
    Command("reopen-tab", "Reopen last closed", "File", "<Control><Shift>t"),
    Command("close-window", "Close window", "File", "<Control>q"),
    Command("settings", "Preferences", "File", "<Control>comma"),
    # Navigation the toolkit's own conventions put on function keys.
    Command("goto-definition", "Go to definition", "Navigate", "F12"),
    Command("find-references", "Find all references", "Navigate", "<Shift>F12"),
    # requirements.md asks for F11 by name, and it was never bound.
    Command("full-screen", "Full screen", "View", "F11"),
    # **The key people press out of VS Code muscle memory.** It cannot make a
    # second cursor — GtkSourceView 5 has no API for one — so it does the useful
    # half and says, once, what it cannot do and what to use instead. A dead key
    # that answers is worth more than a dead key.
    Command("select-next-occurrence", "Select the next occurrence", "Edit", "<Control>d"),
    Command("select-all-occurrences", "Select all occurrences", "Edit", "<Alt>F3"),
    Command("select-enclosing-block", "Expand the selection", "Edit", "<Control><Shift>m"),
    Command("goto-matching-bracket", "Go to the matching brace", "Navigate", "<Control>m"),
    # Navigation history, which the application did not have at all.
    Command("go-back", "Back", "Navigate", "<Alt>Left"),
    Command("go-forward", "Forward", "Navigate", "<Alt>Right"),
    Command("switch-file", "Switch file", "Navigate", "<Control>Tab"),
    Command("goto-problem", "Go to problem", "Navigate", "F8"),
    Command("docs-for-resource", "Documentation for this resource", "Navigate", "F1"),
    # Stopping a run, on the key every terminal-shaped tool uses for it.
    Command("cancel-run", "Cancel the run", "Terraform", "<Control>period"),
    Command("check-drift", "Check for drift", "Terraform", None),
    Command("stacks", "Stacks", "Terraform", None),
    # The three presets. **A preset is not a mode**: touching any single panel
    # afterwards simply leaves it behind.
    Command("layout-focus", "Focus", "View", "<Control><Shift>F11"),
    Command("layout-work", "Work", "View", None),
    Command("layout-review", "Review", "View", None),
    Command("toggle-change-map", "Change map", "View", None),
    Command("toggle-status-bar", "Verdict line", "View", None),
    Command("limits", "What Backsight will not do", "Help", None),
)


@dataclass(frozen=True)
class Conflict:
    """Two commands asking for the same key."""

    accelerator: str
    actions: tuple[str, ...]

    def __str__(self) -> str:
        return f"{self.accelerator} is bound to {' and '.join(self.actions)}"


class Unbindable(Exception):
    """An attempt to remove one of the two keys everything else rests on."""

    def __init__(self, action: str) -> None:
        super().__init__(
            f"{action} cannot be unbound. It is how the rest of the application "
            "is reached when everything else is hidden."
        )


@dataclass
class Keymap:
    """The bindings in effect, and anything wrong with them."""

    commands: dict[str, Command]

    @classmethod
    def build(cls, overrides: dict[str, str | None] | None = None) -> Keymap:
        """Defaults, with the settings file applied over them."""
        commands = {command.action: command for command in DEFAULTS}
        for action, accelerator in (overrides or {}).items():
            existing = commands.get(action)
            if existing is None:
                # A binding for something that does not exist is a typo in a file
                # somebody wrote, and silence would hide it.
                raise KeyError(f"no command named {action}")
            if accelerator in (None, "") and existing.is_floor:
                raise Unbindable(action)
            commands[action] = Command(
                action=existing.action,
                label=existing.label,
                section=existing.section,
                accelerator=accelerator or None,
            )
        return cls(commands=commands)

    def accelerator(self, action: str) -> str | None:
        command = self.commands.get(action)
        return command.accelerator if command else None

    def conflicts(self) -> list[Conflict]:
        """Every key wanted by more than one command."""
        by_key: dict[str, list[str]] = {}
        for command in self.commands.values():
            if command.accelerator:
                by_key.setdefault(command.accelerator, []).append(command.action)
        return [
            Conflict(accelerator=key, actions=tuple(sorted(actions)))
            for key, actions in sorted(by_key.items())
            if len(actions) > 1
        ]

    def sections(self) -> dict[str, list[Command]]:
        """Grouped the way the keyboard reference shows them."""
        found: dict[str, list[Command]] = {}
        for command in self.commands.values():
            found.setdefault(command.section, []).append(command)
        for commands in found.values():
            commands.sort(key=lambda c: c.label)
        return found


def desktop_conflicts(keymap: Keymap, reserved: set[str]) -> list[str]:
    """Bindings the desktop would take first.

    An application cannot win this argument with the compositor, so the useful
    thing is to say which key will never arrive rather than to let somebody
    wonder why nothing happens.
    """
    return sorted(
        f"{command.accelerator} ({command.label}) is taken by the desktop"
        for command in keymap.commands.values()
        if command.accelerator and command.accelerator in reserved
    )
