"""What an apply looks like while it runs, and what it says when it stops.

Every Terraform tool goes quiet at the moment anxiety peaks. This is the screen
that does not: the same resources the person reviewed, in the order they read
them, each ticking over as the engine reaches it — and, when it ends, whether
the state agrees that it worked.

The three endings are deliberately three, not two. **Done** is every resource
where the plan said it would be. **Stopped part way** is the one no other tool
names: some resources changed, one failed, and the rest were never attempted,
which is three different situations for the reader to be in and needs to be
said in those words. **Nothing started** is the easy one, and saying so plainly
is worth more than a stack trace.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.app.dismissable import dismissable
from backsight.engine.plan.applying import Progress, Stage
from backsight.engine.plan.verifying import Verification
from backsight.engine.plan.view import Action

# Shape, not hue — the consequence colours carry the meaning and the icon
# carries it again for anybody who cannot use the colour.
ICONS = {
    Stage.WAITING: "content-loading-symbolic",
    Stage.RUNNING: "media-playback-start-symbolic",
    Stage.DONE: "object-select-symbolic",
    Stage.FAILED: "dialog-error-symbolic",
    Stage.NEVER_REACHED: "media-playback-stop-symbolic",
}

TONES = {
    Stage.DONE: "tf-safe",
    Stage.FAILED: "tf-irreversible",
    Stage.NEVER_REACHED: "tf-faint",
}

# **Consequence outlives the apply.** A destroy that succeeded is still the row
# somebody is scanning this list to find, and one green over "created",
# "changed", "destroyed" and "replaced" makes the one they want the hardest to
# see. Success is already said by the heading, the bar and the tick; the word
# is free to say what happened to that resource.
DONE_TONES = {
    Action.CREATE: "tf-safe",
    Action.UPDATE: "tf-disruptive",
    Action.DELETE: "tf-irreversible",
    Action.REPLACE: "tf-irreversible",
    Action.READ: "tf-faint",
    Action.NO_OP: "tf-faint",
}

STOPPED = (
    "This apply stopped part way. Some of your infrastructure changed, one "
    "resource failed, and the rest were never started."
)
NOTHING = "Nothing was changed. The apply stopped before it reached anything."


def _took(step) -> str:
    """How long a finished resource took, and nothing for one that has not.

    Finished in under a second is an answer, and a blank would read as "never
    started" — which is a different ending on this screen.
    """
    if step.stage not in (Stage.DONE, Stage.FAILED):
        return ""
    return f"{step.seconds:.0f}s" if step.seconds >= 1 else "<1s"


class ApplyScreen(Adw.Bin):
    """The resources, their progress, and the verdict when it is over."""

    def __init__(
        self,
        on_close: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._on_close = on_close
        self._on_stop = on_stop
        self._rows: dict[str, tuple[Gtk.Image, Gtk.Label, Gtk.Label]] = {}

        self._heading = Gtk.Label(xalign=0.0, wrap=True)
        self._heading.add_css_class("tf-strong")

        self._elapsed = Gtk.Label(xalign=0.0)
        self._elapsed.add_css_class("tf-small")
        self._elapsed.add_css_class("tf-faint")

        self._bar = Gtk.ProgressBar(show_text=False)
        self._bar.add_css_class("tf-apply-progress")

        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self._list)

        # What the state says once it is over. Absent until then, because a
        # verdict with nothing behind it is the claim this must never make.
        self._verdict = Gtk.Label(xalign=0.0, wrap=True)
        self._verdict.add_css_class("tf-small")
        self._verdict.set_visible(False)

        # **The one control while something irreversible is happening.** One
        # SIGINT is a graceful shutdown to the engine: the resource in flight
        # finishes, nothing further starts, and the state is written. Cancelling
        # from a menu is not this, and it is not on the screen being watched.
        self._stop = Gtk.Button(label="Stop after this resource")
        self._stop.add_css_class("tf-quiet")
        self._stop.set_halign(Gtk.Align.END)
        self._stop.set_visible(False)
        self._stop.connect("clicked", lambda *_: self._asked_to_stop())

        self._close = Gtk.Button(label="Close")
        self._close.add_css_class("tf-quiet")
        self._close.set_halign(Gtk.Align.END)
        self._close.set_visible(False)
        self._close.connect("clicked", lambda *_: self._on_close() if self._on_close else None)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(12)
        box.append(self._heading)
        box.append(self._elapsed)
        self._closing = Gtk.Label(xalign=0.0, wrap=True)
        self._closing.add_css_class("tf-small")
        self._closing.add_css_class("tf-faint")
        self._closing.set_visible(False)
        box.append(self._closing)
        box.append(self._bar)
        box.append(scroller)
        box.append(self._verdict)
        box.append(self._stop)
        box.append(self._close)
        self.set_child(box)

    def _asked_to_stop(self) -> None:
        """Asks once, and says it is being asked — the engine decides when."""
        self._stop.set_sensitive(False)
        self._stop.set_label("Stopping after this resource…")
        if self._on_stop is not None:
            self._on_stop()

    def say_about_closing(self, said: str) -> None:
        """What closing this window does, while there is something to say."""
        self._closing.set_text(said)
        self._closing.set_visible(bool(said))

    def begin(self, progress: Progress, where: str = "") -> None:
        """Draws the plan as a list of things about to happen."""
        while (child := self._list.get_first_child()) is not None:
            self._list.remove(child)
        self._rows = {}
        for step in progress.steps:
            icon = Gtk.Image.new_from_icon_name(ICONS[step.stage])
            name = Gtk.Label(label=step.address, xalign=0.0, hexpand=True)
            name.add_css_class("tf-mono")
            name.add_css_class("tf-small")
            said = Gtk.Label(label=step.word, xalign=1.0)
            said.add_css_class("tf-small")
            said.add_css_class("tf-faint")
            # Which resource is slow is the question somebody watching this has.
            # Tabular and right-aligned so the column reads as a column and does
            # not shift as a figure grows.
            took = Gtk.Label(label="", xalign=1.0, width_chars=6)
            took.add_css_class("tf-small")
            took.add_css_class("tf-faint")
            took.add_css_class("tf-mono")
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row.append(icon)
            row.append(name)
            row.append(said)
            row.append(took)
            self._list.append(row)
            self._rows[step.address] = (icon, said, took)
        count = len(progress.steps)
        self._heading.set_text(
            f"Applying {count} change{'' if count == 1 else 's'}{f' to {where}' if where else ''}"
        )
        self._verdict.set_visible(False)
        self._close.set_visible(False)
        self._stop.set_visible(self._on_stop is not None)
        self._bar.set_fraction(0.0)
        self.show(progress)

    def show(self, progress: Progress, *, elapsed: float = 0.0) -> None:
        """Moves each row to wherever its resource has got to."""
        for step in progress.steps:
            found = self._rows.get(step.address)
            if found is None:
                continue
            icon, said, took = found
            icon.set_from_icon_name(ICONS[step.stage])
            said.set_text(step.word)
            took.set_text(_took(step))
            for tone in (*TONES.values(), *DONE_TONES.values()):
                said.remove_css_class(tone)
            tone = (
                DONE_TONES.get(step.action, "tf-safe")
                if step.stage is Stage.DONE
                else TONES.get(step.stage)
            )
            if tone:
                said.add_css_class(tone)
        total = len(progress.steps) or 1
        settled = sum(1 for step in progress.steps if step.stage is not Stage.WAITING)
        self._bar.set_fraction(min(1.0, settled / total))
        if elapsed:
            self._elapsed.set_text(f"{elapsed:.0f}s")

    def finished(self, progress: Progress, verification: Verification | None = None) -> None:
        """The three endings, each said in the words a person would use."""
        self.show(progress)
        # How much of the plan actually happened, not how much of it was
        # attempted. A full bar over "stopped part way" is the screen
        # contradicting its own headline.
        total = len(progress.steps) or 1
        self._bar.set_fraction(progress.done / total)
        self._bar.remove_css_class("tf-bar-stopped")
        if progress.done < total:
            self._bar.add_css_class("tf-bar-stopped")
        self._close.set_visible(True)
        self._stop.set_visible(False)

        if progress.is_partial:
            self._heading.set_text(STOPPED)
            self._heading.add_css_class("tf-irreversible")
        elif not any(step.changed_something for step in progress.steps):
            # Everything was still waiting when it stopped — the engine failed
            # before it reached anything. Keyed on what moved rather than on
            # there being a failure, because a failed resource has already moved
            # and that branch could never be reached.
            self._heading.set_text(NOTHING)
        else:
            done = progress.done
            self._heading.set_text(f"Applied {done} change{'' if done == 1 else 's'}")
            self._heading.remove_css_class("tf-irreversible")

        said = []
        if progress.failure:
            said.append(progress.failure)
        if verification is not None:
            said.append(verification.summary)
        self._verdict.set_text("\n".join(said))
        self._verdict.set_visible(bool(said))
        if verification is not None and not verification.ok:
            self._verdict.add_css_class("tf-irreversible")
        else:
            self._verdict.remove_css_class("tf-irreversible")

    @property
    def heading(self) -> str:
        return self._heading.get_text()

    @property
    def verdict(self) -> str:
        return self._verdict.get_text()

    def said_about(self, address: str) -> str:
        found = self._rows.get(address)
        return found[1].get_text() if found else ""


class ApplyWindow(Adw.Window):
    """The apply, in a window of its own.

    Its own window rather than a panel, because an apply is a moment rather
    than a surface — and while one is running there is nothing useful to do in
    the editor behind it.

    **It closes whenever somebody wants it to**, including mid-apply. It used
    to refuse until the engine stopped, on the reasoning that there is no
    cancelling an apply half way — which is true and is not a reason to trap
    anybody. Closing this window does not stop the apply: the engine carries on
    and what it printed is kept. Refusing the close removed the rest of the
    application from somebody for as long as an apply took, and if the engine
    ever hung it removed it for good.
    """

    def __init__(
        self,
        parent: Gtk.Window | None = None,
        on_stop: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(
            title="Apply",
            modal=True,
            transient_for=parent,
            default_width=560,
            default_height=520,
        )
        self.screen = ApplyScreen(on_close=self.close, on_stop=on_stop)
        self._running = False
        dismissable(self, self.screen, title="Apply")

    def begin(self, progress, where: str = "") -> None:
        self._running = True
        self.screen.begin(progress, where)
        self.screen.say_about_closing(
            "Closing this does not stop the apply. It carries on, and what it printed is kept."
        )

    def show(self, progress, *, elapsed: float = 0.0) -> None:
        self.screen.show(progress, elapsed=elapsed)

    def finished(self, progress, verification=None) -> None:
        self._running = False
        self.screen.say_about_closing("")
        self.screen.finished(progress, verification)
