"""Staging, committing and pushing, so nobody switches to a terminal mid-plan.

Switching is where the plan somebody was reading gets lost, which is the whole
reason this is here rather than being somebody else's job.

Two rules on the screen. **Nothing is staged that was not clicked** — there is
no "stage everything" button, because everything is rarely what anybody means
and a commit is hard to take back. And **push asks**, every time: it is
outward-facing, somebody else can pull it a second later, and no amount of
undo in this window reaches them.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.engine.vcs.working import Change, State, Working

NOTHING = "Nothing has changed here"

# What each state is called on screen, in the words somebody would use.
WORDS = {
    State.STAGED: "staged",
    State.CHANGED: "changed",
    State.BOTH: "staged, with more since",
    State.UNTRACKED: "new",
    State.CONFLICTED: "conflicted",
}


class GitPanel(Adw.Bin):
    """What has changed, what is staged, and the two things you can do."""

    def __init__(
        self,
        *,
        on_stage: Callable[[list[str]], None] | None = None,
        on_unstage: Callable[[list[str]], None] | None = None,
        on_commit: Callable[[str], None] | None = None,
        on_push: Callable[[], None] | None = None,
        on_open: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self._on_stage = on_stage
        self._on_unstage = on_unstage
        self._on_commit = on_commit
        self._on_push = on_push
        self._on_open = on_open
        self._working = Working()

        self._branch = Gtk.Label(xalign=0.0, wrap=True)
        self._branch.add_css_class("tf-small")

        self._files = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        listed = Gtk.ScrolledWindow(vexpand=True)
        listed.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        listed.set_min_content_height(150)
        listed.set_child(self._files)

        self.message = Gtk.Entry(placeholder_text="What this change does, in one line")
        self.message.set_hexpand(True)
        self.message.connect("activate", lambda *_: self._commit())

        self._commit_button = Gtk.Button(label="Commit")
        self._commit_button.add_css_class("tf-primary")
        self._commit_button.set_sensitive(False)
        self._commit_button.connect("clicked", lambda *_: self._commit())

        self._push_button = Gtk.Button(label="Push…")
        self._push_button.add_css_class("tf-quiet")
        self._push_button.set_tooltip_text("Sends it. Somebody else can pull it a second later.")
        # Refused until something has looked. A push is outward-facing and
        # nothing here can take it back, so the safe state is the starting one.
        self._push_button.set_sensitive(False)
        self._push_button.connect("clicked", lambda *_: self._on_push() if self._on_push else None)

        doing = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        doing.append(self.message)
        doing.append(self._commit_button)
        doing.append(self._push_button)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(10 if edge in ("top", "bottom") else 12)
        box.append(self._branch)
        box.append(listed)
        box.append(doing)
        self.set_child(box)
        self.show(Working())

    @property
    def branch_line(self) -> str:
        return self._branch.get_text()

    def rows(self) -> list[str]:
        found = []
        child = self._files.get_first_child()
        while child is not None:
            found.append(getattr(child, "said", ""))
            child = child.get_next_sibling()
        return found

    @property
    def can_commit(self) -> bool:
        return self._commit_button.get_sensitive()

    def show(self, working: Working) -> None:
        """What is here now."""
        self._working = working
        while (child := self._files.get_first_child()) is not None:
            self._files.remove(child)
        anything = working.changes or working.unreadable
        self._branch.set_text(working.summary if anything else NOTHING)
        for change in working.changes:
            self._files.append(self._row(change))
        self._commit_button.set_sensitive(working.can_commit)
        self._push_button.set_sensitive(working.can_push)

    def _row(self, change: Change) -> Gtk.Widget:
        name = Gtk.Button(label=change.path)
        name.add_css_class("tf-link")
        name.set_halign(Gtk.Align.START)
        name.set_hexpand(True)
        name.connect(
            "clicked", lambda *_a, p=change.path: self._on_open(p) if self._on_open else None
        )

        said = Gtk.Label(label=WORDS.get(change.state, change.state.value), xalign=1.0)
        said.add_css_class("tf-micro")
        said.add_css_class("tf-faint")

        # One button per file, and no "stage everything": everything is rarely
        # what anybody means and a commit is hard to take back.
        doing = Gtk.Button(label="Unstage" if change.is_staged else "Stage")
        doing.add_css_class("tf-quiet")
        doing.connect("clicked", lambda *_a, c=change: self._moved(c))

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.append(name)
        row.append(said)
        row.append(doing)
        row.said = f"{change.path} — {WORDS.get(change.state, '')}"
        return row

    def _moved(self, change: Change) -> None:
        if change.is_staged:
            if self._on_unstage is not None:
                self._on_unstage([change.path])
        elif self._on_stage is not None:
            self._on_stage([change.path])

    def _commit(self) -> None:
        said = self.message.get_text().strip()
        if not said or not self._working.can_commit:
            return
        if self._on_commit is not None:
            self._on_commit(said)
        self.message.set_text("")
