"""The plan, on the right of the window.

Every row carries a mark and a word as well as a colour, because NFR-15 says
destroy and replace may never be told apart by colour alone — and this is the
panel where getting that wrong costs somebody a database.

No colour is written here. The tone names a role and `app/theme.py` decides what
that looks like in whichever scheme the desktop is using.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.app import empty_state
from backsight.engine.plan.model import Plan
from backsight.engine.plan.repair import explain
from backsight.engine.plan.view import Row, headline, rows, warning


class PlanPanel(Adw.Bin):
    """Shows one plan, or says why there is not one."""

    def __init__(self, on_open: Callable[[str], None] | None = None) -> None:
        super().__init__()
        # What a click on a row does. The inventory has said *jump to the source
        # line* since it was written and nothing did it: the rows were boxes
        # with no gesture on them, so the one navigation a plan is read for was
        # keyboard-only in a panel with no keyboard path to a row either.
        self._on_open = on_open
        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._headline = Gtk.Label(xalign=0.0)
        self._headline.add_css_class("tf-medium")
        self._warning = Gtk.Label(xalign=0.0, wrap=True)
        self._warning.add_css_class("tf-blocked")
        self._warning.set_visible(False)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(10)
        # Enough that the last row can be scrolled clear of the footer below
        # rather than sitting half-hidden behind its top edge.
        box.set_margin_bottom(24)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.append(self._headline)
        box.append(self._warning)
        box.append(self._list)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        # Reports what its content needs rather than its own minimum, so the
        # drawer can be sized to the panel and capped. Without this a scroller
        # asks for almost nothing and every panel opens clipped.
        scroller.set_propagate_natural_height(True)
        scroller.set_child(box)
        self.set_child(scroller)
        self.waiting("Open a workspace and save a file")

    def waiting(self, why: str) -> None:
        """No plan yet, and the reason there is not one.

        A heading reading "Plan" over an empty box says nothing the tab above it
        has not already said, so there is no heading — what is true is centred,
        and why it is true sits under it.
        """
        self._headline.set_visible(False)
        self._warning.set_visible(False)
        self._clear()
        self._list.append(empty_state.build("No plan yet", why, glyph="◆"))

    def failed(
        self,
        why: str,
        found: list | None = None,
        on_show_output=None,
        source: dict[str, str] | None = None,
        on_open=None,
        on_fix=None,
        warnings: list | None = None,
    ) -> None:
        """One block per thing the engine complained about, and nothing else.

        There is no "Plan failed" heading. The blocks below say what failed, and
        a heading above them is the same error told a second time before the
        first one has been read.
        """
        self._headline.set_visible(False)
        self._warning.set_visible(False)
        self._clear()

        for diagnostic in found or []:
            text = (source or {}).get(diagnostic.path, "")
            self._list.append(_diagnostic_widget(diagnostic, text, on_open, on_fix))

        if not found:
            detail = Gtk.Label(label=why, xalign=0.0, wrap=True)
            detail.add_css_class("tf-small")
            self._list.append(detail)

        # Only where nothing could be read out of the output. Each diagnostic
        # already carries its own verbatim text, and the whole run is what the
        # Console tab is for — a second button to almost the same words is the
        # duplication this panel was rebuilt to remove.
        if warnings:
            self._list.append(_warnings(warnings))

        if on_show_output is not None and not found:
            raw = Gtk.Button(label="Full output")
            raw.add_css_class("tf-quiet")
            raw.set_halign(Gtk.Align.START)
            raw.set_margin_top(4)
            raw.connect("clicked", lambda *_: on_show_output())
            self._list.append(raw)

    def show(
        self,
        plan: Plan,
        warnings: list | None = None,
        *,
        source_map=None,
        estimate=None,
    ) -> None:
        self._headline.set_visible(True)
        self._headline.set_label(headline(plan))
        alarm = warning(plan)
        self._warning.set_label(alarm)
        self._warning.set_visible(bool(alarm))
        self._clear()
        arranged = rows(plan, source_map=source_map, estimate=estimate)
        # Grouped by consequence, worst first, because that is the order a
        # person needs to read them in. A list sorted by address makes somebody
        # hunt for the destroy among the tag changes.
        for level in LEVELS:
            found = [row for row in arranged if CONSEQUENCE.get(row.tone) == level]
            if found:
                self._list.append(_group(level, found, self._on_open))
        # Under the changes, never in front of them. A warning did not stop
        # anything, and the person came here for the plan.
        if warnings:
            self._list.append(_warnings(warnings))

    def _clear(self) -> None:
        while (child := self._list.get_first_child()) is not None:
            self._list.remove(child)


# Which consequence each plan action carries, and the order they are read in.
CONSEQUENCE = {
    "destroy": "irreversible",
    "replace": "irreversible",
    "change": "disruptive",
    "add": "safe",
    "none": "safe",
}

LEVELS = ("irreversible", "disruptive", "safe")

# The gutter keeps replace as its own colour, because a replace is neither a
# create nor a destroy and it is the change people misread most.
TONE_CLASS = {
    "add": "tf-safe",
    "change": "tf-disruptive",
    "replace": "tf-replace",
    "destroy": "tf-irreversible",
    "none": "tf-faint",
}

WORDS = {
    "irreversible": "Irreversible",
    "disruptive": "Disruptive",
    "safe": "Safe",
}

# What each level means, said once at the top of its group rather than on
# every row.
MEANS = {
    "irreversible": "no rollback",
    "disruptive": "brief downtime, recoverable",
    "safe": "additive, reversible",
}


def _diagnostic_widget(diagnostic, source="", on_open=None, on_fix=None) -> Gtk.Widget:
    """One thing the engine complained about, said once.

    The title is written for the reader; the engine's own words stay verbatim
    under `Show the original`, collapsed. A fix appears only where it follows from the
    text with nothing guessed — see `engine/plan/repair.py`.
    """
    said = explain(diagnostic, source)

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.set_margin_bottom(14)

    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=9)
    header.set_valign(Gtk.Align.BASELINE)
    # The word as well as the colour, per NFR-15. An error and a warning may
    # never be told apart by hue alone.
    severity = Gtk.Label(label=diagnostic.severity, xalign=0.0)
    severity.add_css_class("tf-micro")
    severity.add_css_class("tf-medium")
    severity.add_css_class("tf-irreversible" if diagnostic.is_error else "tf-disruptive")
    severity.set_valign(Gtk.Align.BASELINE)
    header.append(severity)
    title = Gtk.Label(label=said.title, xalign=0.0, wrap=True)
    title.add_css_class("tf-strong")
    header.append(title)
    if diagnostic.where:
        where = Gtk.Button(label=diagnostic.where)
        where.add_css_class("tf-link")
        where.set_valign(Gtk.Align.BASELINE)
        where.set_tooltip_text(f"Open {diagnostic.path} at line {diagnostic.line}")
        if on_open is None:
            where.set_sensitive(False)
        else:
            where.connect("clicked", lambda *_: on_open(diagnostic.path, diagnostic.line))
        header.append(where)
    box.append(header)

    if said.explanation:
        detail = Gtk.Label(label=said.explanation, xalign=0.0, wrap=True, selectable=True)
        detail.add_css_class("tf-dim")
        detail.set_max_width_chars(64)
        box.append(detail)

    if said.repair is not None:
        box.append(_fix_preview(said.repair))

    actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    if said.repair is not None and on_fix is not None:
        fix = Gtk.Button(label="Fix and re-plan")
        # Quiet. The footer holds the one primary action on this screen, and
        # two filled buttons make neither of them the obvious next thing.
        fix.add_css_class("tf-quiet")
        fix.connect("clicked", lambda *_: on_fix(diagnostic, said.repair))
        actions.append(fix)
    if diagnostic.where and on_open is not None:
        go = Gtk.Button(label="Go to line")
        go.add_css_class("tf-quiet")
        go.connect("clicked", lambda *_: on_open(diagnostic.path, diagnostic.line))
        actions.append(go)
    if actions.get_first_child() is not None:
        box.append(actions)

    if diagnostic.raw:
        box.append(_raw(diagnostic.raw))
    return box


# More than this and they are a wall rather than a list, so they fold away.
FOLD_WARNINGS_PAST = 3


def _warnings(found: list) -> Gtk.Widget:
    """What the engine wants noticed, none of which stopped anything."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.set_margin_top(10)
    for said in found:
        box.append(_diagnostic_widget(said))

    heading = f"{len(found)} warning{'' if len(found) == 1 else 's'}, none blocking"
    if len(found) <= FOLD_WARNINGS_PAST:
        titled = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        label = Gtk.Label(label=heading, xalign=0.0)
        label.add_css_class("tf-small")
        label.add_css_class("tf-disruptive")
        titled.append(label)
        titled.append(box)
        return titled

    expander = Gtk.Expander(label=heading)
    expander.add_css_class("tf-small")
    expander.set_child(box)
    return expander


def _fix_preview(repair) -> Gtk.Widget:
    """The edit, as two lines, before anybody agrees to it."""
    frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    frame.add_css_class("tf-fix-preview")
    for text, tone in (
        (f"− {repair.before.strip()}", "tf-line-destroy"),
        (f"+ {repair.after.strip()}", "tf-line-create"),
    ):
        line = Gtk.Label(label=text, xalign=0.0, selectable=True)
        line.add_css_class("tf-mono")
        line.add_css_class("tf-small")
        line.add_css_class(tone)
        frame.append(line)
    return frame


def _raw(text: str) -> Gtk.Widget:
    """What the engine actually printed, collapsed.

    Never removed. A translation nobody can check against the original is just
    a different opacity.
    """
    body = Gtk.Label(label=text, xalign=0.0, wrap=True, selectable=True)
    body.add_css_class("tf-mono")
    body.add_css_class("tf-micro")
    body.add_css_class("tf-faint")
    body.set_margin_top(6)
    expander = Gtk.Expander(label="Show the original")
    expander.add_css_class("tf-small")
    expander.set_child(body)
    return expander


def _group(
    level: str, found: list[Row], on_open: Callable[[str], None] | None = None
) -> Gtk.Widget:
    """One consequence group.

    **A 2px rule down the left edge, and nothing else.** Only a blocker fills a
    background, and the difference between "this is dangerous" and "this will
    not run" is carried by fill rather than by hue.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    box.add_css_class("tf-group")
    box.add_css_class(f"tf-{level}")
    box.set_margin_bottom(8)

    header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    header.add_css_class("tf-group-header")
    header.add_css_class(f"tf-{level}")
    # Small and uppercase: a group label names a section rather than competing
    # with the addresses under it.
    title = Gtk.Label(label=f"{WORDS[level].upper()} · {len(found)}", xalign=0.0)
    title.add_css_class("tf-group-label")
    header.append(title)
    means = Gtk.Label(label=MEANS[level], xalign=1.0, hexpand=True)
    means.add_css_class("tf-small")
    header.append(means)
    box.append(header)

    for row in found:
        box.append(_row_widget(row, on_open))
    return box


def _row_widget(row: Row, on_open: Callable[[str], None] | None = None) -> Gtk.Widget:
    """One change, and a way to get to it.

    **The whole row is the target.** A plan is read to find the one thing worth
    going to look at, and asking somebody to hit a link inside the row is
    asking them to aim at the thing they have already found.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    for edge in ("top", "bottom", "start", "end"):
        getattr(box, f"set_margin_{edge}")(9 if edge in ("top", "bottom") else 10)

    line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    mark = Gtk.Label(label=row.mark)
    mark.add_css_class("tf-mark")
    mark.add_css_class(TONE_CLASS.get(row.tone, "tf-faint"))
    line.append(mark)

    word = Gtk.Label(label=row.label, xalign=0.0)
    word.add_css_class("tf-small")
    word.add_css_class(TONE_CLASS.get(row.tone, "tf-faint"))
    line.append(word)
    box.append(line)

    address = Gtk.Label(label=row.address, xalign=0.0, wrap=True, selectable=True)
    address.add_css_class("tf-mono")
    box.append(address)

    # Where it was written and what it costs, on one line under the address.
    # Two facts a reviewer needs and neither of them worth a line of its own.
    facts = " · ".join(said for said in (row.where, row.cost) if said)
    if facts:
        said = Gtk.Label(label=facts, xalign=0.0)
        said.add_css_class("tf-micro")
        said.add_css_class("tf-faint")
        box.append(said)

    if row.reason:
        reason = Gtk.Label(label=row.reason, xalign=0.0, wrap=True)
        reason.add_css_class("tf-small")
        reason.add_css_class("tf-faint")
        box.append(reason)

    if on_open is None:
        return box
    # A button rather than a gesture: it takes the keyboard as well, so the
    # same row is reachable by Tab and by pointer, and it carries the tooltip
    # saying what pressing it does.
    button = Gtk.Button(child=box)
    button.add_css_class("flat")
    button.add_css_class("tf-plan-row")
    button.set_tooltip_text(f"Go to {row.address}" + (f" — {row.where}" if row.where else ""))
    button.connect("clicked", lambda *_a, address=row.address: on_open(address))
    return button
