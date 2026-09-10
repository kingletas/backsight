"""The keyboard reference, which is one of the two things that cannot be hidden.

What first run teaches is one thing — the command palette. From there
everything is searchable. This is the other half of the floor: a list of every
binding, grouped, always reachable, and never unbound.

It also reports conflicts, because a keymap that silently drops one of two
bindings makes "why doesn't my key work" unanswerable.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.engine.settings.keys import Keymap

# The order sections are shown in. Panels first: this dialog is most often opened
# by somebody who has lost one.
SECTIONS = ("Panels", "Navigate", "Terraform", "File")


def pretty(accelerator: str | None) -> str:
    """`<Control><Shift>p` as a person reads it."""
    if not accelerator:
        return "unbound"
    ok, key, modifiers = Gtk.accelerator_parse(accelerator)
    return Gtk.accelerator_get_label(key, modifiers) if ok else accelerator


class KeyboardReference(Adw.Window):
    """Every binding, grouped, with anything wrong with them at the top."""

    def __init__(self, keymap: Keymap, parent: Gtk.Window | None = None) -> None:
        super().__init__(
            title="Keyboard reference",
            modal=True,
            transient_for=parent,
            default_width=560,
            default_height=620,
        )
        self.keymap = keymap

        page = Adw.PreferencesPage()
        for conflict in keymap.conflicts():
            # Named rather than resolved. Load order deciding it is what makes
            # the cause invisible.
            group = Adw.PreferencesGroup(title="Conflicts")
            row = Adw.ActionRow(title=str(conflict), subtitle="Only one of these will fire.")
            group.add(row)
            page.add(group)

        sections = keymap.sections()
        for name in list(SECTIONS) + [s for s in sorted(sections) if s not in SECTIONS]:
            commands = sections.get(name)
            if not commands:
                continue
            group = Adw.PreferencesGroup(title=name)
            for command in commands:
                row = Adw.ActionRow(title=command.label)
                shortcut = Gtk.Label(label=pretty(command.accelerator))
                shortcut.add_css_class("tf-faint")
                shortcut.add_css_class("tf-small")
                shortcut.add_css_class("tf-mono")
                row.add_suffix(shortcut)
                group.add(row)
            page.add(group)

        header = Adw.HeaderBar()
        layout = Adw.ToolbarView()
        layout.add_top_bar(header)
        layout.set_content(page)
        self.set_content(layout)

        # Escape closes every panel in this application, with no exceptions.
        escape = Gtk.ShortcutController()
        escape.add_shortcut(
            Gtk.Shortcut(
                trigger=Gtk.ShortcutTrigger.parse_string("Escape"),
                action=Gtk.CallbackAction.new(lambda *_: bool(self.close()) or True),
            )
        )
        self.add_controller(escape)
