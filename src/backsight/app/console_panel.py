"""The expression console: type an expression, see what it evaluates to.

FR-DBG-01. One process per expression, because the engine's console exits on
the first error — so the history on screen is ours to keep, and it is the only
record of the session there will be. It is never written to disk: the engine
redacts sensitive values on its own, and a log would be the copy that is not
redacted by anything.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk, Pango

from backsight.engine.console.evaluation import Evaluation

PROMPT = "›"
WITHHELD = "The engine withheld this because it is marked sensitive."
NOT_YET = "This has not been applied yet, so there is no value to read."
EMPTY = "Type an expression to evaluate it against this workspace."

# How tall the history is allowed to grow before it scrolls inside itself.
HEIGHT = 260


class ConsolePanel(Adw.Bin):
    """An entry, and everything asked so far with what came back."""

    def __init__(self, on_evaluate: Callable[[str], None] | None = None) -> None:
        super().__init__()
        self._on_evaluate = on_evaluate
        self._history: list[str] = []
        self._recalled = 0
        self._directory: Path | None = None

        self._log = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._empty = Gtk.Label(label=EMPTY, xalign=0.0, wrap=True)
        self._empty.add_css_class("tf-small")
        self._empty.add_css_class("tf-faint")
        self._log.append(self._empty)

        # **The transcript takes the height and the prompt is pinned under
        # it.** Growing to fit the content put the prompt half way up a tall
        # drawer with empty space below it, which reads as a line of text that
        # happens to have a box round it rather than as the thing you type in.
        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_min_content_height(HEIGHT)
        # A well, so the record of what has been asked and the thing you ask
        # with are two surfaces rather than one.
        scroller.add_css_class("tf-sunken")
        scroller.set_child(self._log)
        self._scroller = scroller

        self._entry = Gtk.Entry(placeholder_text="length(var.subnets)")
        self._entry.set_hexpand(True)
        self._entry.connect("activate", lambda *_: self.submit())
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self._entry.add_controller(keys)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.add_css_class("tf-console-prompt")
        prompt = Gtk.Label(label=PROMPT)
        prompt.add_css_class("tf-faint")
        prompt.add_css_class("tf-small")
        row.append(prompt)
        row.append(self._entry)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(10 if edge in ("top", "bottom") else 12)
        box.append(scroller)
        box.append(row)
        self.set_child(box)

    @property
    def entry(self) -> Gtk.Entry:
        return self._entry

    @property
    def history(self) -> list[str]:
        return list(self._history)

    def submit(self) -> None:
        """Sends whatever is typed, and clears the entry ready for the next."""
        text = self._entry.get_text().strip()
        if not text:
            return
        self._history.append(text)
        self._recalled = len(self._history)
        self._entry.set_text("")
        if self._on_evaluate is not None:
            self._on_evaluate(text)

    def show(self, answer: Evaluation) -> None:
        """Appends one exchange and scrolls to it."""
        self._empty.set_visible(False)
        self._log.append(self._exchange(answer))
        adjustment = self._scroller.get_vadjustment()
        adjustment.set_value(adjustment.get_upper())

    def clear(self) -> None:
        """Forgets the session. The engine kept none of it either."""
        child = self._log.get_first_child()
        while child is not None:
            following = child.get_next_sibling()
            if child is not self._empty:
                self._log.remove(child)
            child = following
        self._empty.set_visible(True)
        self._history.clear()
        self._recalled = 0

    def _exchange(self, answer: Evaluation) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        asked = Gtk.Label(label=f"{PROMPT} {answer.expression}", xalign=0.0, wrap=True)
        asked.add_css_class("tf-mono")
        asked.set_selectable(True)
        box.append(asked)

        if answer.failure is not None:
            summary = Gtk.Label(label=answer.failure.summary, xalign=0.0, wrap=True)
            # **At a word, never mid-sentence.** The default wraps anywhere it
            # can, and an engine error is long enough that it always could — so
            # every failure read as though it had been cut with scissors.
            summary.set_wrap_mode(Pango.WrapMode.WORD)
            summary.add_css_class("tf-irreversible")
            summary.set_selectable(True)
            box.append(summary)
            if answer.failure.detail:
                detail = Gtk.Label(label=answer.failure.detail, xalign=0.0, wrap=True)
                detail.set_wrap_mode(Pango.WrapMode.WORD)
                detail.add_css_class("tf-small")
                detail.add_css_class("tf-faint")
                detail.set_selectable(True)
                box.append(detail)
            return box

        value = Gtk.Label(label=answer.value or "(no value)", xalign=0.0, wrap=True)
        value.add_css_class("tf-mono")
        value.set_selectable(True)
        box.append(value)

        note = WITHHELD if answer.redacted else NOT_YET if answer.unapplied else ""
        if note:
            explanation = Gtk.Label(label=note, xalign=0.0, wrap=True)
            explanation.set_wrap_mode(Pango.WrapMode.WORD)
            explanation.add_css_class("tf-small")
            explanation.add_css_class("tf-faint")
            box.append(explanation)
        return box

    def _on_key(self, _controller, keyval: int, _code: int, _state) -> bool:
        """Up and Down walk back through what was asked, as a shell does."""
        from gi.repository import Gdk  # noqa: PLC0415

        if not self._history:
            return False
        if keyval == Gdk.KEY_Up:
            self._recalled = max(0, self._recalled - 1)
        elif keyval == Gdk.KEY_Down:
            self._recalled = min(len(self._history), self._recalled + 1)
        else:
            return False
        recalled = self._history[self._recalled] if self._recalled < len(self._history) else ""
        self._entry.set_text(recalled)
        self._entry.set_position(-1)
        return True
