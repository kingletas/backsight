"""What a panel says when it has nothing in it, in one place so it is one thing.

**An empty state answers three questions in this order: what is true, why you
are seeing it, and what to do next.** If there is no next action it stops at two
and does not invent a button — an empty state whose button does nothing useful
is worse than an empty state.

Centred, quiet, with a glyph from the family it belongs to. Every one of these
used to be a left-aligned sentence at the top of a large empty rectangle, which
reads as a render that stopped half way rather than as a considered nothing.

**A panel with nothing to say is not the same as a panel that failed**, and the
difference is the whole reason this is a component rather than a label: the
wording, the alignment and the weight are decided once, so no panel can
accidentally make its own quiet case look loud.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk


def build(
    what: str,
    why: str = "",
    *,
    glyph: str = "",
    action: str = "",
    on_act: Callable[[], None] | None = None,
) -> Gtk.Widget:
    """One empty state.

    `what` is true right now. `why` says how it came to be true, and where the
    thing that changes it lives. `action` is offered **only** when pressing it
    would actually change the state — never as decoration on a dead end.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    box.add_css_class("tf-empty")
    box.set_valign(Gtk.Align.CENTER)
    box.set_halign(Gtk.Align.CENTER)
    box.set_vexpand(True)
    box.set_hexpand(True)

    if glyph:
        mark = Gtk.Label(label=glyph)
        mark.add_css_class("tf-empty-glyph")
        box.append(mark)

    heading = Gtk.Label(label=what, justify=Gtk.Justification.CENTER, wrap=True)
    heading.add_css_class("tf-medium")
    box.append(heading)

    if why:
        # Helper text takes a full stop; a heading, a button and a label never
        # do. The two are different kinds of sentence.
        body = Gtk.Label(label=why, wrap=True, justify=Gtk.Justification.CENTER)
        body.add_css_class("tf-small")
        body.add_css_class("tf-faint")
        body.set_max_width_chars(44)
        box.append(body)

    if action and on_act is not None:
        button = Gtk.Button(label=action)
        button.add_css_class("tf-quiet")
        button.set_halign(Gtk.Align.CENTER)
        button.set_margin_top(4)
        button.connect("clicked", lambda *_: on_act())
        box.append(button)
    return box
