"""What changed outside Terraform, and where.

The status bar said `3 drifted` and the number went nowhere. Drift is arguably
the strongest thing this application can say — it is true about somebody's
infrastructure whether or not the window is open — and a count with nothing
behind it is the opposite of that.

Each row names the resource and the attributes that moved, with the value it was
and the value it is. What it deliberately does not do is say which of them
matters: an autoscaler moving a desired count is the system working and somebody
editing a security group by hand is not, and nothing here can tell them apart.
Putting the attribute name in front of a person lets them judge in a second.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.engine.plan.drifting import Drift

NOTHING_YET = "Run a drift check to see what has changed outside Terraform"


class DriftPanel(Adw.Bin):
    """Every resource reality has moved away from, and what moved."""

    def __init__(
        self,
        on_open: Callable[[str], None] | None = None,
        on_check: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self._on_open = on_open
        self._on_check = on_check

        self._headline = Gtk.Label(xalign=0.0, wrap=True)
        self._headline.add_css_class("tf-small")

        self._rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_propagate_natural_height(True)
        scroller.set_max_content_height(260)
        scroller.set_child(self._rows)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for edge in ("top", "bottom", "start", "end"):
            getattr(box, f"set_margin_{edge}")(10 if edge in ("top", "bottom") else 12)
        # The empty state says to run a drift check. This is how you run it.
        self.check = Gtk.Button(label="Check for drift")
        self.check.set_halign(Gtk.Align.START)
        self.check.connect("clicked", lambda *_: self._on_check() if self._on_check else None)

        box.append(self._headline)
        box.append(self.check)
        box.append(scroller)
        self.set_child(box)
        self.show(Drift())

    def show(self, drift: Drift) -> None:
        """Draws what the last check found, or what would fill this."""
        while (child := self._rows.get_first_child()) is not None:
            self._rows.remove(child)
        self._headline.set_text(drift.headline)
        self._headline.remove_css_class("tf-faint")
        self._headline.remove_css_class("tf-disruptive")
        if drift.failure or drift.resources:
            self._headline.add_css_class("tf-disruptive")
        else:
            self._headline.add_css_class("tf-faint")
        for found in drift.resources:
            self._rows.append(self._row(found))

    def _row(self, found) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        address = Gtk.Button(label=found.address)
        address.add_css_class("tf-link")
        address.set_halign(Gtk.Align.START)
        address.set_tooltip_text("Go to where this is declared")
        address.connect(
            "clicked", lambda *_a, a=found.address: self._on_open(a) if self._on_open else None
        )
        box.append(address)

        said = Gtk.Label(label=found.summary, xalign=0.0, wrap=True)
        said.add_css_class("tf-small")
        said.add_css_class("tf-irreversible" if found.is_gone else "tf-disruptive")
        box.append(said)

        for difference in found.differences[:6]:
            line = Gtk.Label(label=str(difference), xalign=0.0, wrap=True)
            line.add_css_class("tf-micro")
            line.add_css_class("tf-mono")
            line.add_css_class("tf-faint")
            box.append(line)
        return box

    @property
    def headline(self) -> str:
        return self._headline.get_text()

    def addresses(self) -> list[str]:
        found = []
        child = self._rows.get_first_child()
        while child is not None:
            button = child.get_first_child()
            if isinstance(button, Gtk.Button):
                found.append(button.get_label())
            child = child.get_next_sibling()
        return found
