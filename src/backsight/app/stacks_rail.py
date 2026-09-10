"""The stacks section of the left rail.

The design puts stacks beside files: **upstream drift on `data` is visible while
you are editing `api`, which is the thing no file tree can tell you.**

The rail shows every stack in apply order, what each one binds to, and — for
the stack the open file belongs to — what a change to it reaches. That last
part is FR-STK-06, the half of dependency management that belongs on a desktop.

Nothing here applies anything. v1 computes the order and a person executes it
one stack at a time — DD-15.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.engine.stacks.graph import Radius, cycles, stacks_in_order
from backsight.engine.stacks.model import Definitions, Stack

NONE_DECLARED = "No stacks declared"
# "Deployable units and their edges" is graph vocabulary in a sidebar. This
# says what a stack is for, in the words somebody would use about their own
# infrastructure.
HOW_TO = "Group modules that deploy together, so you can plan and apply them as one."

# Shown beside a stack that cannot be placed in the apply order.
IN_A_CYCLE = "in a cycle"

# Shown on a stack that has been left behind by something it depends on. The
# plan it last ran was computed from data that has since moved.
STALE = "planned before something it depends on was applied"


class StacksRail(Adw.Bin):
    """Every stack, in the order they would be applied."""

    def __init__(self, on_open: Callable[[Stack], None] | None = None) -> None:
        super().__init__()
        self._on_open = on_open
        self._rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        self._note = Gtk.Label(xalign=0.0, wrap=True)
        self._note.add_css_class("tf-small")
        self._note.add_css_class("tf-faint")

        self._problems = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        # No heading of its own: the rail section it sits in carries the name,
        # and two headings for one section is what the rail used to look like.
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.append(self._note)
        box.append(self._problems)
        box.append(self._rows)
        self.set_child(box)
        self.show(Definitions())

    def show(
        self,
        definitions: Definitions,
        radius: Radius | None = None,
        *,
        behind: set[str] | None = None,
    ) -> None:
        """Draws the graph, the radius of whatever is being edited, and what is stale.

        `behind` is the stacks that have been left behind by something they
        depend on — the same set the verdict line's chip counts. It is named on
        the row rather than only in the chip, because the chip says *something*
        is stale and this is where you find out which.
        """
        self._clear()
        if not definitions.stacks:
            # An undeclared graph is the ordinary case, not a fault. Say what
            # would fill it rather than showing an empty heading.
            self._note.set_text(NONE_DECLARED if definitions.is_declared else HOW_TO)
            self._note.set_visible(True)
            self._draw_problems(definitions)
            return

        caught = {name for cycle in cycles(definitions) for name in cycle.names}
        self._note.set_text(f"{len(definitions.stacks)} in apply order")
        self._note.set_visible(True)
        self._draw_problems(definitions)

        reached = {consumer.name: consumer for consumer in (radius.consumers if radius else [])}
        for stack in stacks_in_order(definitions):
            self._rows.append(
                _row(
                    stack,
                    in_cycle=stack.name in caught,
                    is_open=bool(radius and stack.name == radius.stack),
                    consumer=reached.get(stack.name),
                    on_open=self._on_open,
                    behind=bool(behind and stack.name in behind),
                )
            )

    def _draw_problems(self, definitions: Definitions) -> None:
        """Every problem, in full. A count would hide which stack is broken."""
        for cycle in cycles(definitions):
            self._problems.append(_problem(f"Cycle: {cycle}"))
        for problem in definitions.problems:
            self._problems.append(_problem(str(problem)))

    def _clear(self) -> None:
        for box in (self._rows, self._problems):
            while (child := box.get_first_child()) is not None:
                box.remove(child)


def _problem(text: str) -> Gtk.Widget:
    label = Gtk.Label(label=text, xalign=0.0, wrap=True)
    label.add_css_class("tf-small")
    label.add_css_class("tf-irreversible")
    return label


def _row(
    stack: Stack,
    *,
    in_cycle: bool,
    is_open: bool,
    consumer,
    on_open: Callable[[Stack], None] | None,
    behind: bool = False,
) -> Gtk.Widget:
    """One stack: its name, where it deploys, and why it is in the radius."""
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    name = Gtk.Label(label=stack.name, xalign=0.0)
    if is_open:
        name.add_css_class("tf-medium")
    if behind:
        name.add_css_class("tf-disruptive")
    box.append(name)

    if behind:
        # The chip in the verdict line says *something* is stale. This is where
        # you find out which, and it is the only reason to open this view on an
        # ordinary day.
        said = Gtk.Label(label=STALE, xalign=0.0, wrap=True)
        said.add_css_class("tf-small")
        said.add_css_class("tf-disruptive")
        box.append(said)

    detail = _detail(stack, in_cycle=in_cycle, consumer=consumer)
    if detail:
        line = Gtk.Label(label=detail, xalign=0.0, wrap=True)
        line.add_css_class("tf-small")
        line.add_css_class("tf-irreversible" if in_cycle else "tf-faint")
        box.append(line)

    button = Gtk.Button(child=box)
    button.add_css_class("flat")
    button.set_tooltip_text(_tooltip(stack))
    if on_open is not None:
        button.connect("clicked", lambda *_a, s=stack: on_open(s))
    return button


def _detail(stack: Stack, *, in_cycle: bool, consumer) -> str:
    if in_cycle:
        return IN_A_CYCLE
    if consumer is not None:
        return consumer.because()
    return stack.environment or stack.path


def _tooltip(stack: Stack) -> str:
    """Everything the stack declares, for the one place there is room for it."""
    said = [stack.path]
    if stack.environment:
        said.append(stack.environment)
    if stack.binding.is_stated:
        said.append(str(stack.binding))
    if stack.outputs:
        said.append(f"publishes {', '.join(stack.outputs)}")
    for upstream in stack.upstream:
        consumed = ", ".join(stack.needs[upstream]) or "no outputs"
        said.append(f"needs {upstream} — {consumed}")
    return "\n".join(said)
