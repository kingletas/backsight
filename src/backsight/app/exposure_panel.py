"""What the plan exposes to the internet, and the path that proves it.

The compression: the path reads as **one line of text** rather than a
card. The card in sheet one was decoration, and the line loses nothing.

FR-EXP-06 is why the path is shown at all: a reviewer has to be able to check
the claim without trusting us. An answer with no evidence behind it is an
opinion about somebody's network.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.app import empty_state
from backsight.engine.insight.exposure import Finding, Reach, Report

ARROW = " → "

# Shape as well as colour, matching the gutter marks.
MARKS = {
    Reach.EXPOSED: "●",
    Reach.UNKNOWN: "?",
    Reach.NOT_EXPOSED: "·",
}

TONES = {
    Reach.EXPOSED: "tf-irreversible",
    Reach.UNKNOWN: "tf-disruptive",
    Reach.NOT_EXPOSED: "tf-faint",
}

NOTHING = "Nothing in this plan is reachable from the internet."


class ExposurePanel(Adw.Bin):
    """Every finding, worst first, each with the path behind it."""

    def __init__(self) -> None:
        super().__init__()
        self.count = 0
        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._headline = Gtk.Label(xalign=0.0)
        self._headline.add_css_class("tf-medium")
        self._caveat = Gtk.Label(xalign=0.0, wrap=True)
        self._caveat.add_css_class("tf-small")
        self._caveat.add_css_class("tf-disruptive")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(12 if edge in ("start", "end") else 10)
        box.append(self._headline)
        box.append(self._caveat)
        box.append(self._list)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        # Reports what its content needs rather than its own minimum, so the
        # drawer can be sized to the panel and capped. Without this a scroller
        # asks for almost nothing and every panel opens clipped.
        scroller.set_propagate_natural_height(True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(box)
        self.set_child(scroller)
        self.waiting("")

    def waiting(self, why: str) -> None:
        """Says what would fill this, which is not the same as being empty.

        The tab above already says "Exposure", so this does not repeat it —
        what it says is why there is nothing under it yet, centred, with the
        thing that would change it.
        """
        self._clear()
        self.count = 0
        self._headline.set_visible(False)
        self._caveat.set_visible(False)
        self._list.append(
            empty_state.build(
                "Public access has not been analysed",
                why or "Run a plan, and what it would make reachable will be here.",
                glyph="●",
            )
        )

    def show(self, report: Report) -> None:
        """Draws a report. Worst first, because that is the reading order."""
        self._clear()
        exposed = [finding for finding in report.findings if finding.is_exposed]
        # What the tab badge and the verdict-line chip both count, held here so
        # neither has to reach into the report and reach a different answer.
        self.count = len(exposed)
        unknown = [finding for finding in report.findings if finding.is_partial]

        self._headline.set_text(_headline(exposed, unknown))
        self._headline.set_visible(True)
        # A partial answer that does not say it is partial is a wrong answer.
        caveat = "; ".join(report.partial_because) if report.partial else ""
        self._caveat.set_text(caveat)
        self._caveat.set_visible(bool(caveat))

        if not exposed and not unknown:
            # A clean answer is still an answer, and it is centred like every
            # other nothing in this application rather than being a sentence in
            # the top-left of a large empty rectangle.
            self._headline.set_visible(False)
            self._list.append(empty_state.build("Nothing exposed", NOTHING, glyph="●"))
            return
        for finding in (*exposed, *unknown):
            self._list.append(_row(finding))

    def _clear(self) -> None:
        while (child := self._list.get_first_child()) is not None:
            self._list.remove(child)


def _headline(exposed: list[Finding], unknown: list[Finding]) -> str:
    """Only counts that are not zero, so nothing reads as five negatives."""
    said = []
    if exposed:
        said.append(f"{len(exposed)} reachable from the internet")
    if unknown:
        said.append(f"{len(unknown)} undecided")
    return " · ".join(said) if said else "Nothing exposed"


def _row(finding: Finding) -> Gtk.Widget:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

    heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    mark = Gtk.Label(label=MARKS[finding.reach])
    mark.add_css_class("tf-mark")
    mark.add_css_class(TONES[finding.reach])
    heading.append(mark)
    address = Gtk.Label(label=finding.address, xalign=0.0, hexpand=True)
    address.add_css_class("tf-mono")
    address.set_selectable(True)
    heading.append(address)
    box.append(heading)

    if finding.path:
        # One line, not a card. Each hop carries its own reason on the tooltip
        # so the compression costs nothing.
        path = Gtk.Label(label=ARROW.join(hop.address for hop in finding.path), xalign=0.0)
        path.add_css_class("tf-small")
        path.add_css_class("tf-faint")
        path.set_wrap(True)
        path.set_selectable(True)
        path.set_tooltip_text("\n".join(finding.evidence()))
        box.append(path)
    elif finding.detail:
        detail = Gtk.Label(label=finding.detail, xalign=0.0, wrap=True)
        detail.add_css_class("tf-small")
        detail.add_css_class("tf-faint")
        box.append(detail)
    return box
