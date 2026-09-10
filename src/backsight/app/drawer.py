"""The plan drawer: detail, invoked rather than resident.

**Escape always closes it.** No panel in this application needs a mouse to
dismiss. It holds the panels that answer a question you asked; the rail holds
the tree you were going to look at anyway.

**All ten tabs are always there**, quiet when they have nothing to say and
carrying a count when they do. Hiding a tab hides the capability, and a
capability nobody can see is one nobody uses.

The design names eight. Docs, Git and Output are real surfaces it did not
enumerate, and the same rule that forbids hiding a tab is what puts them here.

The close control is a button at the **right end of the strip**, not a hint
sitting in the tab row. That hint was 12 characters of the row's width, and it
was taking exactly the space the last tab needed — `Drift` was clipped in every
screenshot the project ever took of itself with the drawer open.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.engine.insight.sections import EXPOSURE

# What changes, what it exposes, what proves it, what lets you ask something
# the other three did not answer, and the raw thing all four are summaries of.
TABS = (
    "Changes",
    EXPOSURE,
    "Cost",
    "Tests",
    "Console",
    "Drift",
    "Library",
    "Docs",
    "Git",
    "Output",
)

# **No icons.** Measured: nine tabs with an icon each ask for 1221px, and the
# drawer has about 1020 at a 1280 window with the rail open — so one label was
# always cut, and it was always the same one. Ten labels on their own fit with
# room to spare, and a tab strip is a row of words rather than a toolbar.

DISMISS = "Esc to close"


class Drawer(Adw.Bin):
    """One drawer, ten tabs, and a way out at the end of the row."""

    def __init__(self, panels: dict[str, Gtk.Widget], on_close: Callable[[], None] | None = None):
        super().__init__()
        self._on_close = on_close
        # An Adw.ViewStack rather than a Gtk.Stack, for one reason: its pages
        # carry a badge. **A tab with something to say says how much**, and a
        # tab with nothing to say stays quiet rather than showing a nought.
        self._stack = Adw.ViewStack()
        # **Nothing here animates**, and an `Adw.ViewStack` has no transition to
        # turn off — which is the reason it is the right widget for this.
        # Switching tab is not a journey, and a crossfade between two panels of
        # dense text is the one thing that makes a drawer feel slow.

        for name in TABS:
            panel = panels.get(name)
            if panel is None:
                # A tab with nothing behind it would be a promise the drawer
                # cannot keep, so it is absent rather than empty.
                continue
            self._stack.add_titled(panel, name.lower(), name)

        # A strip of our own rather than a stock switcher. The stock ones each
        # gave up something this design needs: `Gtk.StackSwitcher` has nowhere
        # to put a count, and `Adw.ViewSwitcher` reserves an icon slot per tab
        # and truncates a label to pay for it.
        self._switcher = _Strip(self._stack)
        self._switcher.set_halign(Gtk.Align.START)
        # Nine tabs are wider than a narrow window, and a switcher that asks
        # for its full width makes the whole drawer ask for it — which pushed
        # the inspector off the screen entirely. It scrolls instead.
        self._along = Gtk.ScrolledWindow()
        # EXTERNAL, not AUTOMATIC: it still scrolls, and it draws no scrollbar.
        # AUTOMATIC lays an overlay bar across the tabs whenever the pointer is
        # anywhere near them.
        self._along.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        self._along.set_hexpand(True)
        self._along.set_child(self._switcher)

        # The room belongs to the tabs. This is a control at the end of the
        # row rather than a sentence inside it: a glyph and a tooltip cost 24
        # pixels where the hint cost the width of the last tab.
        dismiss = Gtk.Button(icon_name="window-close-symbolic")
        dismiss.add_css_class("flat")
        dismiss.set_tooltip_text(DISMISS)
        dismiss.set_valign(Gtk.Align.CENTER)
        dismiss.connect("clicked", lambda *_: self.close())
        self._dismiss = dismiss

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.add_css_class("tf-drawer-header")
        for edge in ("start", "end"):
            getattr(header, f"set_margin_{edge}")(10)
        header.set_margin_top(6)
        header.set_margin_bottom(6)
        header.append(self._along)
        header.append(dismiss)

        # Opening a tab by key or palette must show you which one you are on.
        self._stack.connect("notify::visible-child", lambda *_: self._bring_the_tab_into_view())
        # And again once there is a width to scroll within. Choosing a tab
        # before the drawer has been laid out divides nothing by nothing, so
        # the first tab opened stayed off the edge until something else moved.
        self._along.get_hadjustment().connect("changed", lambda *_: self._bring_the_tab_into_view())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add_css_class("tf-drawer")
        box.append(header)
        box.append(Gtk.Separator())
        box.append(self._stack)
        self.set_child(box)

    @property
    def section(self) -> str:
        """Which tab is showing."""
        name = self._stack.get_visible_child_name()
        return name.capitalize() if name else ""

    def count(self, name: str, found: int) -> None:
        """How much a tab has to say, as a count on the tab itself.

        Quiet when there is nothing — **a badge reading nought is a badge people
        stop reading**, and it takes the badge that means something down with it.
        """
        self._switcher.count(name, found)

    @property
    def sections(self) -> list[str]:
        """The tabs that actually exist, in order."""
        return [page.get_title() for page in self._stack.get_pages()]

    def show_section(self, name: str) -> bool:
        """Opens a named tab. False when there is no such tab to open."""
        wanted = name.strip().lower()
        if self._stack.get_child_by_name(wanted) is None:
            return False
        self._stack.set_visible_child_name(wanted)
        return True

    def _bring_the_tab_into_view(self) -> None:
        """Scrolls the switcher so the open tab is one you can see.

        Narrower than nine tabs is the normal case, so some are always off the
        edge. The one you are reading must never be among them.
        """
        showing = self._stack.get_visible_child()
        if showing is None:
            return
        pages = self._stack.get_pages()
        wanted = next(
            (at for at in range(pages.get_n_items()) if pages.get_item(at).get_child() is showing),
            None,
        )
        if wanted is None:
            return
        button = _nth_button(self._switcher, wanted)
        if button is None:
            return
        found, box = button.compute_bounds(self._switcher)
        if not found:
            return
        along = self._along.get_hadjustment()
        if along.get_page_size() <= 0:
            # No width yet, so nothing is off the edge to bring back.
            return
        left, right = box.origin.x, box.origin.x + box.size.width
        if left < along.get_value():
            along.set_value(left)
        elif right > along.get_value() + along.get_page_size():
            along.set_value(right - along.get_page_size())

    def close(self) -> None:
        if self._on_close is not None:
            self._on_close()


def _nth_button(switcher: Gtk.Widget, wanted: int) -> Gtk.Widget | None:
    """The nth tab in a switcher, whatever it wraps its buttons in.

    Asked of the widget tree rather than assumed: a `Gtk.StackSwitcher` holds
    its buttons directly and an `Adw.ViewSwitcher` holds them inside a box, and
    a walk that assumes one silently finds nothing in the other — which reads
    as "no tab is off the edge" rather than as a fault.
    """
    found: list[Gtk.Widget] = []

    def walk(widget: Gtk.Widget) -> None:
        child = widget.get_first_child()
        while child is not None:
            if isinstance(child, Gtk.ToggleButton | Gtk.Button):
                found.append(child)
            else:
                walk(child)
            child = child.get_next_sibling()

    walk(switcher)
    return found[wanted] if wanted < len(found) else None


class _Strip(Gtk.Box):
    """The drawer's tabs: a row of words, each with a count when it has one.

    Twenty-eight pixels, flat, and the one in front takes the body's own
    surface. Nothing here is clever; it exists because the two stock switchers
    each refuse one thing this design asks for, and a tab strip is small enough
    to own.
    """

    def __init__(self, stack) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add_css_class("tf-drawer-tabs")
        self._stack = stack
        self._tabs: dict[str, Gtk.ToggleButton] = {}
        self._counts: dict[str, Gtk.Label] = {}
        self._settling = False

        pages = stack.get_pages()
        for at in range(pages.get_n_items()):
            page = pages.get_item(at)
            self._add(page.get_name(), page.get_title())
        stack.connect("notify::visible-child-name", lambda *_: self._follow())
        self._follow()

    def _add(self, name: str, title: str) -> None:
        label = Gtk.Label(label=title)
        found = Gtk.Label()
        found.add_css_class("tf-count")
        found.set_visible(False)
        inside = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        inside.append(label)
        inside.append(found)

        tab = Gtk.ToggleButton(child=inside)
        tab.add_css_class("flat")
        tab.add_css_class("tf-drawer-tab")
        tab.connect("toggled", lambda button, n=name: self._chosen(button, n))
        self.append(tab)
        self._tabs[name] = tab
        self._counts[name] = found

    def _chosen(self, button: Gtk.ToggleButton, name: str) -> None:
        if self._settling or not button.get_active():
            return
        self._stack.set_visible_child_name(name)

    def _follow(self) -> None:
        """Keeps the pressed tab in step with whatever the stack is showing."""
        showing = self._stack.get_visible_child_name()
        self._settling = True
        for name, tab in self._tabs.items():
            tab.set_active(name == showing)
        self._settling = False

    def count(self, name: str, found: int) -> None:
        label = self._counts.get(name.strip().lower())
        if label is None:
            return
        label.set_label(str(found))
        label.set_visible(found > 0)
