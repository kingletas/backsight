"""Which panels exist, what state each is in, and how every one is got back.

Shortcuts do not answer "how do I get it back" on their own, because
the thing that was lost is the knowledge of which shortcut. **Every panel has at
least one keyboard path and one mouse path**, and there is a test that hides all
of them and checks each is still reachable both ways.

Two surfaces are the floor and cannot be hidden at all: the command palette and
the keyboard reference. Everything else rests on them.

The other rule worth stating: **collapsed is not hidden.** Collapsed leaves a
clickable strip, so a mis-click never loses a feature permanently, which is why
collapsed rather than hidden is the default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Visibility(Enum):
    """Three states, and the middle one is the reason mis-clicks are survivable."""

    SHOWN = "shown"
    COLLAPSED = "collapsed"
    HIDDEN = "hidden"

    @property
    def is_reachable_by_pointing(self) -> bool:
        """Collapsed leaves an eight pixel strip. Hidden leaves nothing."""
        return self is not Visibility.HIDDEN


@dataclass(frozen=True)
class Panel:
    """One surface, and every way back to it."""

    name: str
    label: str
    action: str | None
    mouse_paths: tuple[str, ...]
    collapsible: bool = True
    browsable: bool = False
    default: Visibility = Visibility.COLLAPSED

    def keyboard_paths(self, keymap) -> tuple[str, ...]:
        """Its own key, plus the palette, which can reach anything."""
        found = []
        if self.action:
            accelerator = keymap.accelerator(self.action)
            if accelerator:
                found.append(accelerator)
        palette = keymap.accelerator("palette")
        if palette:
            found.append(f"{palette} → {self.label}")
        return tuple(found)


PANELS: tuple[Panel, ...] = (
    Panel(
        name="left_rail",
        label="Left rail",
        action="toggle-left-rail",
        mouse_paths=("chrome right-click", "View menu", "strip click"),
        # Stated, so it agrees with `layout.left_rail` in the settings. The
        # field default was collapsed and the setting said shown, which is two
        # answers to one question with nothing to say which was meant.
        default=Visibility.SHOWN,
    ),
    Panel(
        name="plan_drawer",
        label="Plan drawer",
        action="toggle-plan-drawer",
        mouse_paths=("status segment click", "View menu"),
        collapsible=False,
        default=Visibility.HIDDEN,
    ),
    Panel(
        name="console",
        label="Console",
        action="toggle-console",
        mouse_paths=("View menu", "chrome right-click"),
        collapsible=False,
        default=Visibility.HIDDEN,
    ),
    Panel(
        name="menu_bar",
        label="Menu bar",
        action="toggle-menu-bar",
        mouse_paths=("primary menu", "chrome right-click"),
        collapsible=False,
        browsable=True,
        # **Off by default.** Its eight menus are in the primary menu, so with
        # the bar on they would be in two places at once — and the row itself
        # ran 62% empty while costing 28 pixels of every screen.
        default=Visibility.HIDDEN,
    ),
    Panel(
        name="hamburger",
        label="Primary menu",
        action=None,
        # Always there, and it cannot be hidden: it is the last browsable
        # surface, and what it carries changes with the menu bar rather than
        # duplicating it.
        mouse_paths=("always present",),
        collapsible=False,
        browsable=True,
        default=Visibility.SHOWN,
    ),
    Panel(
        name="status_bar",
        label="Verdict line",
        action=None,
        mouse_paths=("chrome right-click", "View menu"),
        collapsible=False,
        default=Visibility.SHOWN,
    ),
    Panel(
        name="change_map",
        label="Change map",
        action=None,
        mouse_paths=("View menu", "chrome right-click"),
        collapsible=False,
        default=Visibility.SHOWN,
    ),
)

BY_NAME = {panel.name: panel for panel in PANELS}

# "Hiding a browsable surface reveals the next one down; hiding the last one is
# refused." A chain rather than a set, so hiding the menu bar can never leave
# nothing browsable.
#
# **The primary menu is now the resident one and the bar is the option**, which
# is the reverse of how this started. It carries the eight menus while the bar
# is off and hands them over when it comes on, so the two never hold the same
# item at once — and there is always something to point at, whatever else has
# been turned off.
BROWSABLE_CHAIN = ("menu_bar", "hamburger")


class LastBrowsableSurface(Exception):
    """Refusing to hide the last thing that can be browsed."""

    def __init__(self, label: str) -> None:
        super().__init__(
            f"{label} is the last surface that can be browsed. Hiding it would "
            "leave no way to find anything by pointing."
        )


@dataclass
class Layout:
    """What is shown right now, per workspace."""

    states: dict[str, Visibility] = field(default_factory=dict)

    @classmethod
    def default(cls) -> Layout:
        return cls(states={panel.name: panel.default for panel in PANELS})

    @classmethod
    def opening(cls, settings) -> Layout:
        """The default layout, with whatever settings say about it applied.

        `layout.left_rail` and `layout.change_map` had defaults and no reader,
        so the window opened the same way whatever either of them said.
        """
        layout = cls.default()
        for panel, key in (("left_rail", "layout.left_rail"), ("change_map", "layout.change_map")):
            wanted = str(settings.get(key, "") or "")
            try:
                layout.set(panel, Visibility(wanted))
            except ValueError:
                continue
        return layout

    def visibility(self, name: str) -> Visibility:
        return self.states.get(name, BY_NAME[name].default)

    def is_shown(self, name: str) -> bool:
        return self.visibility(name) is not Visibility.HIDDEN

    def set(self, name: str, visibility: Visibility) -> None:
        panel = BY_NAME[name]
        if visibility is Visibility.COLLAPSED and not panel.collapsible:
            visibility = Visibility.HIDDEN
        if visibility is Visibility.HIDDEN and panel.browsable:
            successor = self._next_browsable(name)
            if successor is None:
                raise LastBrowsableSurface(panel.label)
            self.states[successor] = Visibility.SHOWN
        self.states[name] = visibility
        # The last surface in the chain stays whatever else happens: it is what
        # the refusal above protects, and putting it away because something
        # earlier came back would be the same hole by another route.
        if visibility is not Visibility.HIDDEN and panel.browsable:
            successor = self._next_browsable(name)
            if successor is not None and self._next_browsable(successor) is not None:
                self.states[successor] = Visibility.HIDDEN

    def toggle(self, name: str) -> Visibility:
        """Shown becomes collapsed where that is possible, otherwise hidden."""
        current = self.visibility(name)
        panel = BY_NAME[name]
        if current is Visibility.SHOWN:
            self.set(name, Visibility.COLLAPSED if panel.collapsible else Visibility.HIDDEN)
        else:
            self.set(name, Visibility.SHOWN)
        return self.visibility(name)

    def hide_everything(self) -> None:
        """What plate 42 does. The refusal keeps one browsable surface alive."""
        for panel in PANELS:
            try:
                self.set(panel.name, Visibility.HIDDEN)
            except LastBrowsableSurface:
                continue

    def reset(self) -> None:
        """Always one click away, from every chrome menu."""
        self.states = {panel.name: panel.default for panel in PANELS}

    def _next_browsable(self, name: str) -> str | None:
        """The surface that takes over when this one is hidden."""
        if name not in BROWSABLE_CHAIN:
            return None
        index = BROWSABLE_CHAIN.index(name)
        remaining = BROWSABLE_CHAIN[index + 1 :]
        return remaining[0] if remaining else None


def restore_paths(panel: Panel, keymap) -> dict[str, tuple[str, ...]]:
    """Every way back to one panel, by kind."""
    return {"keyboard": panel.keyboard_paths(keymap), "mouse": panel.mouse_paths}
