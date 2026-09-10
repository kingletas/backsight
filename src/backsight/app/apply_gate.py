"""The footer: one action, and one specific sentence about it.

The prototype puts this at the foot of the review, and the shape is the whole
argument. Apply is not a button somebody presses on the way past — it is the
end of a page they have read.

Three things still hold:

1. **The environment is typed out by hand** when the plan is irreversible.
   Not a checkbox: a checkbox is one click and so is the mistake.
2. **The button is neutral until the plan is irreversible.** A permanently red
   Apply trains people to ignore red.
3. **Apply appears only when applying is possible.** It is not disabled the rest
   of the time, it is absent, and the footer carries whatever the person should
   actually do next. A dead primary action teaches people that the footer is
   scenery, and then the one time it matters it is scenery.

What the footer should say is decided in `engine/plan/footer.py`. This draws it.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.engine.plan.footer import Footer, Situation, footer

UNLOCK = "Type {environment} to unlock"


class ApplyGate(Adw.Bin):
    """Everything between a plan and the next thing to do about it."""

    def __init__(self, on_apply: Callable[[], None] | None = None) -> None:
        super().__init__()
        self._on_apply = on_apply
        self._run: Callable[[str], None] | None = None
        self._footer: Footer | None = None

        self._confirm = Gtk.Entry(width_chars=18)
        self._confirm.set_visible(False)
        self._confirm.connect("changed", lambda *_: self._refresh())

        self._button = Gtk.Button(label="Run plan")
        self._button.add_css_class("tf-apply")
        self._button.connect("clicked", lambda *_: self._pressed())

        self._hint = Gtk.Label(xalign=0.0, wrap=True, hexpand=True)
        self._hint.add_css_class("tf-micro")
        self._hint.add_css_class("tf-faint")
        self._hint.set_valign(Gtk.Align.CENTER)

        # **Summary left, action right.** Apply is the last thing under the
        # reading rather than the first thing beside it: it sat bottom-left,
        # where a reading starts, which put the irreversible control in front
        # of the sentence explaining it.
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.append(self._hint)
        row.append(self._confirm)
        row.append(self._button)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(10 if edge in ("top", "bottom") else 12)
        box.append(row)
        self.set_child(box)
        self.show(Situation())

    def on_command(self, run: Callable[[str], None]) -> None:
        """What to call when the footer's action is pressed."""
        self._run = run

    @property
    def hint(self) -> str:
        return self._hint.get_label()

    @property
    def action(self) -> str:
        """The label on the one button, or "" when there is no footer."""
        return self._button.get_label() if self.get_visible() else ""

    @property
    def can_apply(self) -> bool:
        return self._button.get_sensitive() and self._is_apply

    @property
    def _is_apply(self) -> bool:
        return self._footer is not None and self._footer.command == "apply"

    def show(self, now: Situation) -> None:
        """Draws whatever the situation says the next action is."""
        self._footer = footer(now)
        # No action means no footer. An empty bar holding the space is the
        # footer claiming there is a decision here.
        self.set_visible(self._footer is not None)
        if self._footer is None:
            return

        self._button.set_label(self._footer.action)
        self._button.remove_css_class("tf-irreversible")
        if self._footer.irreversible:
            self._button.add_css_class("tf-irreversible")

        self._confirm.set_visible(self._footer.wants_confirmation)
        self._confirm.set_placeholder_text(
            f"type {self._footer.confirm} to confirm" if self._footer.wants_confirmation else ""
        )
        if not self._footer.wants_confirmation:
            self._confirm.set_text("")
        self._refresh()

    def _refresh(self) -> None:
        if self._footer is None:
            return
        # The primary action is never disabled. Only the typed confirmation
        # holds it, and the hint says what to type.
        confirmed = not self._footer.wants_confirmation or self._typed_it
        self._button.set_sensitive(confirmed)
        self._hint.set_label(
            UNLOCK.format(environment=self._footer.confirm)
            if not confirmed
            else self._footer.detail
        )

    @property
    def _typed_it(self) -> bool:
        return self._confirm.get_text().strip() == (self._footer.confirm if self._footer else "")

    def _pressed(self) -> None:
        if self._footer is None:
            return
        if self._footer.command == "apply":
            if self._on_apply is not None and self.can_apply:
                self._on_apply()
            return
        if self._run is not None:
            self._run(self._footer.command)
