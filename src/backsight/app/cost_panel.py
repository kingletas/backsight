"""What this plan does to the monthly bill, line by line.

It was a text dump into the output tab — which is where raw engine output goes,
so a considered estimate arrived looking like something a subprocess printed.
The cost chip in the verdict line points here, and a chip that opens a wall of
text is a chip that answers a different question than the one it was clicked on.

**Never a number this does not have.** A usage-priced resource is *not
estimable* rather than nought, because rounding a per-request price to zero is a
confident claim about somebody's money. The engine already gets this right and
this only has to keep it right on screen.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.app import empty_state
from backsight.engine.policy.cost import Estimate, Known

NO_PRICES = (
    "No prices are shipped with this application. A price invented from memory "
    "would be a confident number about your money."
)


class CostPanel(Adw.Bin):
    """The estimate, and what it could not say."""

    def __init__(self) -> None:
        super().__init__()
        self._headline = Gtk.Label(xalign=0.0)
        self._headline.add_css_class("tf-figure")
        self._caveat = Gtk.Label(xalign=0.0, wrap=True)
        self._caveat.add_css_class("tf-small")
        self._caveat.add_css_class("tf-faint")
        self._list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(10 if edge in ("top", "bottom") else 12)
        box.append(self._headline)
        box.append(self._caveat)
        box.append(self._list)

        scroller = Gtk.ScrolledWindow(vexpand=True)
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(box)
        self.set_child(scroller)
        self.waiting()

    def waiting(self, why: str = "") -> None:
        """Nothing to price yet, said once and centred."""
        self._clear()
        self._headline.set_visible(False)
        self._caveat.set_visible(False)
        self._list.append(
            empty_state.build(
                "Nothing priced yet",
                why or "Run a plan, and what it changes about the bill will be here.",
                glyph="$",
            )
        )

    def show(self, estimate: Estimate, *, have_prices: bool = True) -> None:
        """The estimate, worst first — the biggest change to the bill leads."""
        self._clear()
        if not estimate.lines:
            self.waiting("Nothing in this plan costs anything.")
            return
        if not have_prices:
            self.waiting(NO_PRICES)
            return

        self._headline.set_label(estimate.headline)
        self._headline.set_visible(True)
        unknown = len(estimate.unestimable)
        self._caveat.set_label(
            f"{unknown} of {len(estimate.lines)} cannot be estimated: they are priced "
            "per request, per GB or per hour of something."
            if unknown
            else ""
        )
        self._caveat.set_visible(bool(unknown))

        for line in sorted(
            estimate.lines, key=lambda one: (one.is_estimable, -abs(one.difference))
        ):
            self._list.append(_row(line))

    def _clear(self) -> None:
        while (child := self._list.get_first_child()) is not None:
            self._list.remove(child)


def _row(line) -> Gtk.Widget:
    """One resource, what it costs, and how sure that is."""
    address = Gtk.Label(label=line.address, xalign=0.0, hexpand=True)
    address.add_css_class("tf-mono")
    address.add_css_class("tf-small")
    address.set_ellipsize(3)

    said = Gtk.Label(xalign=1.0)
    said.add_css_class("tf-small")
    if line.known is Known.FREE:
        said.set_label("nothing to bill")
        said.add_css_class("tf-faint")
    elif not line.is_estimable:
        said.set_label("not estimable")
        said.add_css_class("tf-faint")
    else:
        sign = "+" if line.difference > 0 else ""
        said.set_label(f"{sign}{line.difference:.2f}")
        said.add_css_class(
            "tf-disruptive" if line.difference > 0 else "tf-safe" if line.difference else "tf-faint"
        )

    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    row.append(address)
    row.append(said)
    return row
