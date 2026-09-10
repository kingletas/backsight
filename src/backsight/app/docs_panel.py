"""Provider documentation, beside the file rather than in a browser tab.

Two things it must do that a browser tab does not. It is **version-matched** —
the page for the provider in the lock file, not the newest, because an argument
that arrived two releases later is a suggestion that will not apply. And its
**examples go into the buffer**, because copying out of a browser is how an
example arrives with the wrong indentation and a stray prompt character.

What it deliberately does not do is render markdown into something pretty. The
prose is read once and acted on; the examples are the part anybody comes back
for, and they are Terraform.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.engine.schema.documentation import Page

NOTHING_YET = "Search for a resource type, or put the caret in one and press Docs for this."
NOT_MIRRORED = "Not mirrored yet. Turn on provider documentation in Preferences to fetch it once."


class DocsPanel(Adw.Bin):
    """One resource's page: what it is, what it takes, and its examples."""

    def __init__(
        self,
        *,
        on_search: Callable[[str], list[tuple[str, str]]] | None = None,
        on_open: Callable[[str], None] | None = None,
        on_insert: Callable[[str], None] | None = None,
        on_caret: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._on_search = on_search
        self._on_open = on_open
        self._on_insert = on_insert
        self._on_caret = on_caret
        self._page: Page | None = None

        self.search = Gtk.SearchEntry(placeholder_text="s3 bucket, instance, dns record…")
        self.search.set_hexpand(True)
        self.search.connect("search-changed", lambda *_: self._look())

        self._matches = Gtk.ListBox()
        self._matches.add_css_class("tf-tree")
        self._matches.connect(
            "row-activated", lambda _l, row: self._open(getattr(row, "subject", ""))
        )
        found = Gtk.ScrolledWindow()
        found.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        found.set_max_content_height(150)
        found.set_propagate_natural_height(True)
        found.set_child(self._matches)
        self._matches_holder = found
        found.set_visible(False)

        self._title = Gtk.Label(xalign=0.0, wrap=True)
        self._title.add_css_class("tf-strong")
        self._summary = Gtk.Label(label=NOTHING_YET, xalign=0.0, wrap=True)
        self._summary.add_css_class("tf-small")
        self._summary.add_css_class("tf-faint")

        self._where = Gtk.Label(xalign=0.0, wrap=True)
        self._where.add_css_class("tf-micro")
        self._where.add_css_class("tf-faint")

        self._prose = Gtk.Label(xalign=0.0, yalign=0.0, wrap=True, selectable=True)
        self._prose.add_css_class("tf-small")
        reading = Gtk.ScrolledWindow(vexpand=True)
        reading.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        reading.set_child(self._prose)

        self._examples = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(10 if edge in ("top", "bottom") else 12)
        # The empty state told people to press a button, and there was no
        # button. This is it: docs for whatever the caret is sitting in.
        self.caret = Gtk.Button(label="Docs for this")
        self.caret.set_tooltip_text("Documentation for the resource the caret is in")
        self.caret.connect("clicked", lambda *_: self._on_caret and self._on_caret())
        looking = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        looking.append(self.search)
        looking.append(self.caret)
        box.append(looking)
        box.append(found)
        box.append(self._title)
        box.append(self._summary)
        box.append(self._where)
        box.append(self._examples)
        box.append(reading)
        self.set_child(box)

    @property
    def summary(self) -> str:
        return self._summary.get_text()

    @property
    def title(self) -> str:
        return self._title.get_text()

    def matches(self) -> list[str]:
        found = []
        row = self._matches.get_first_child()
        while row is not None:
            found.append(getattr(row, "subject", ""))
            row = row.get_next_sibling()
        return found

    def look_for(self, term: str) -> None:
        self.search.set_text(term)
        self._look()

    def _look(self) -> None:
        while (row := self._matches.get_first_child()) is not None:
            self._matches.remove(row)
        term = self.search.get_text().strip()
        if not term or self._on_search is None:
            self._matches_holder.set_visible(False)
            return
        for subject, kind in self._on_search(term)[:12]:
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=f"{subject}", xalign=0.0)
            said = Gtk.Label(label=kind.replace("_", " "), xalign=1.0, hexpand=True)
            said.add_css_class("tf-micro")
            said.add_css_class("tf-faint")
            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            line.append(label)
            line.append(said)
            row.set_child(line)
            row.subject = subject
            self._matches.append(row)
        self._matches_holder.set_visible(bool(self.matches()))

    def _open(self, subject: str) -> None:
        if subject and self._on_open is not None:
            self._on_open(subject)

    def waiting(self, said: str) -> None:
        """What is shown when there is a resource but no page for it."""
        self._page = None
        self._title.set_text("")
        self._summary.set_text(said)
        self._where.set_text("")
        self._prose.set_text("")
        self._draw_examples(())

    def show(self, page: Page) -> None:
        """One page, version-matched, with its examples ready to insert."""
        self._page = page
        self._title.set_text(page.resource)
        self._summary.set_text(page.summary or "This page has no summary.")
        self._where.set_text(f"{page.provider} {page.version}")
        self._prose.set_text(page.text)
        self._draw_examples(page.examples)

    def _draw_examples(self, examples) -> None:
        while (child := self._examples.get_first_child()) is not None:
            self._examples.remove(child)
        for one in examples[:8]:
            self._examples.append(self._example(one))
        self._examples.set_visible(bool(examples))

    def _example(self, example) -> Gtk.Widget:
        button = Gtk.Button(label=f"Insert: {example.title}")
        button.add_css_class("tf-quiet")
        button.set_halign(Gtk.Align.START)
        button.set_tooltip_text(example.body.strip()[:400])
        button.connect(
            "clicked",
            lambda *_a, body=example.body: self._on_insert(body) if self._on_insert else None,
        )
        return button

    def examples(self) -> list[str]:
        found = []
        child = self._examples.get_first_child()
        while child is not None:
            found.append(child.get_label())
            child = child.get_next_sibling()
        return found
