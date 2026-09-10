"""Asking once, at the moment it matters, with the damage named.

The reference menu has "Close Tab(s) — Skip Unsaved" and "Close Tab(s)
— Dismiss Unsaved" as separate items. One of those silently destroys work, its
neighbour does not, and they look identical.

So there is one command, and this dialog. It names the file and how much would
be lost, because *fourteen changed lines is a decision and "unsaved changes" is
a shrug* — and it does not appear at all when nothing would be lost, because
confirming a harmless action teaches people to click through confirmations.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.engine.layout.tabs import Scope, Selection, damage


class Answer(Enum):
    """What the person chose. Every one of them is explicit."""

    CANCEL = "cancel"
    KEEP_OPEN = "keep-open"
    DISCARD = "discard"
    SAVE = "save"


# A question a person would actually ask. Pasting the scope's own name after a
# count produced "Close 2 tabs others?", which nobody noticed because nothing
# called this dialog.
HEADINGS = {
    Scope.THIS: "Close {name}?",
    Scope.OTHERS: "Close the other {tabs}?",
    Scope.LEFT: "Close {tabs} to the left?",
    Scope.RIGHT: "Close {tabs} to the right?",
    Scope.ALL: "Close all {tabs}?",
}


def heading(selection: Selection) -> str:
    """One file is asked about by name; several are asked about by count.

    "Close 1 tab to the right?" makes somebody work out which file that is when
    the dialog already knows.
    """
    tabs = f"{selection.count} tab{'' if selection.count == 1 else 's'}"
    name = selection.tabs[0].path.name if selection.tabs else "this file"
    if selection.count == 1:
        return f"Close {name}?"
    pattern = HEADINGS.get(selection.scope, "Close {tabs}?")
    return pattern.format(tabs=tabs, name=name)


def body(selection: Selection) -> str:
    """One sentence of summary, then the damage file by file."""
    unsaved = selection.unsaved
    if not unsaved:
        return ""
    count = (
        "One has unsaved changes." if len(unsaved) == 1 else f"{len(unsaved)} have unsaved changes."
    )
    return "\n".join([count, "", *damage(selection)])


def ask(
    parent: Gtk.Window,
    selection: Selection,
    then: Callable[[Answer], None],
) -> None:
    """Puts the question, or answers it without asking when nothing is at stake."""
    if not selection.costs_work:
        then(Answer.DISCARD)
        return

    dialog = Adw.MessageDialog(
        transient_for=parent,
        heading=heading(selection),
        body=body(selection),
    )
    dialog.add_response(Answer.CANCEL.value, "Cancel")
    dialog.add_response(Answer.KEEP_OPEN.value, "Keep it open")
    dialog.add_response(Answer.DISCARD.value, "Discard and close")
    dialog.add_response(Answer.SAVE.value, "Save and close")
    dialog.set_response_appearance(Answer.DISCARD.value, Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_response_appearance(Answer.SAVE.value, Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response(Answer.SAVE.value)
    dialog.set_close_response(Answer.CANCEL.value)
    dialog.connect("response", lambda _d, response: then(Answer(response)))
    dialog.present()
