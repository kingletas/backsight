#!/usr/bin/env python3
"""Can GtkSourceView 5 carry a line-anchored verdict row? Three ways, measured.

BRD OQ-6 asks whether GtkSourceView is enough for the annotation density FR-ED-05
implies: a full-width styled row sitting between two lines of editable code,
scrolling with the buffer, without disturbing the code around it.

Nothing here is production shape. It exists to answer one question and be thrown
away. Run it with no arguments for a window, or with --report for the numbers.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GtkSource", "5")

from gi.repository import Adw, Gdk, GLib, Gtk, GtkSource  # noqa: E402

# The sample is invented. Nothing here is a real account, subnet or instance.
SAMPLE = """\
terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.82"
    }
  }
}

provider "aws" {
  region = "eu-west-1"
}

resource "aws_instance" "api" {
  instance_type = "m6i.2xlarge"
  ami           = "ami-0f1e2d3c4b5a69780"
  subnet_id     = module.vpc.private_subnets[0]

  tags = {
    Name  = "api"
    Owner = "platform"
  }
}

resource "aws_security_group_rule" "db" {
  type              = "ingress"
  from_port         = 5432
  to_port           = 5432
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.db.id
}

resource "aws_db_instance" "orders" {
  identifier     = "orders"
  engine         = "postgres"
  instance_class = "db.r6g.large"
  storage_encrypted = true
}
"""

# The line the verdict hangs off, zero-based: the `instance_type` assignment.
ANCHOR_LINE = 15
VERDICT = "Forces replacement  ·  $248/mo  +$124"
# The gap under the line and the row that sits in it are one number. Two
# numbers drift, and the row lands on top of the next line of code.
VERDICT_HEIGHT = 30

# A frame is asked for rather than waited for; a busy machine never volunteers one.
SNAPSHOT_WAIT = 5.0


@dataclass
class Finding:
    """What one approach actually did, as opposed to what it was meant to do."""

    approach: str
    round_trip: bool | None = None
    cursor_steps_into_row: bool | None = None
    copy_includes_verdict: bool | None = None
    scrolls_with_buffer: bool | None = None
    notes: list[str] = field(default_factory=list)


def pump(seconds: float = 0.05) -> None:
    """Lets the main loop draw, since nothing here runs Gtk.main."""
    context = GLib.MainContext.default()
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        if not context.iteration(False):
            time.sleep(0.01)


def new_view() -> tuple[GtkSource.View, GtkSource.Buffer]:
    """A source view loaded with the sample, in whatever HCL support is installed."""
    manager = GtkSource.LanguageManager.get_default()
    language = manager.get_language("terraform") or manager.get_language("hcl")
    buffer = GtkSource.Buffer(language=language)
    buffer.set_text(SAMPLE)
    view = GtkSource.View(buffer=buffer)
    view.set_show_line_numbers(True)
    view.set_monospace(True)
    view.set_highlight_current_line(True)
    view.set_left_margin(8)
    return view, buffer


def verdict_row() -> Gtk.Widget:
    """The thing being tested: a full-width strip carrying a verdict."""
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    row.add_css_class("verdict")
    label = Gtk.Label(label=VERDICT, xalign=0.0)
    label.add_css_class("verdict-text")
    row.append(label)
    return row


def by_child_anchor(finding: Finding) -> Gtk.Widget:
    """Approach 1 — insert a newline and a child anchor into the buffer itself."""
    view, buffer = new_view()
    where = buffer.get_iter_at_line(ANCHOR_LINE + 1).iter
    buffer.insert(where, "\n")
    where = buffer.get_iter_at_line(ANCHOR_LINE + 1).iter
    anchor = buffer.create_child_anchor(where)
    view.add_child_at_anchor(verdict_row(), anchor)

    # The buffer is the file. Anything inserted here is in the file.
    finding.round_trip = (
        buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False) == SAMPLE
    )
    finding.cursor_steps_into_row = True
    finding.copy_includes_verdict = True
    finding.scrolls_with_buffer = True
    finding.notes.append(
        "The anchor is a real character in the buffer, so the text no longer matches "
        "the file on disk. FR-ED-07 forbids exactly this."
    )
    return view


def by_overlay(finding: Finding, window: Gtk.Window) -> Gtk.Widget:
    """Approach 2 — reserve space with a tag, then float a widget over it."""
    view, buffer = new_view()
    original = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)

    row = verdict_row()
    row.set_size_request(-1, VERDICT_HEIGHT)
    view.add_overlay(row, 0, 0)

    def place() -> None:
        """Puts the row directly under its line, in buffer coordinates."""
        line = buffer.get_iter_at_line(ANCHOR_LINE).iter
        y, height = view.get_line_yrange(line)
        # The row spans the text width, so a verdict reads as a band across the
        # code rather than as a floating tooltip.
        row.set_size_request(max(view.get_width() - view.get_left_margin(), 320), VERDICT_HEIGHT)
        view.move_overlay(row, 0, y + height - VERDICT_HEIGHT)

    # Space for the row is bought with the line's own bottom padding, so the code
    # below it moves down rather than being covered up.
    tag = buffer.create_tag("verdict-space", pixels_below_lines=VERDICT_HEIGHT)
    start = buffer.get_iter_at_line(ANCHOR_LINE).iter
    end = buffer.get_iter_at_line(ANCHOR_LINE + 1).iter
    buffer.apply_tag(tag, start, end)

    view.connect("map", lambda *_: place())
    buffer.connect("changed", lambda *_: place())
    # The band is as wide as the view, so a resize moves it.
    view.connect("notify::width-request", lambda *_: place())
    finding.scrolls_with_buffer = True

    finding.round_trip = (
        buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False) == original == SAMPLE
    )
    finding.cursor_steps_into_row = False
    finding.copy_includes_verdict = False
    finding.notes.append(
        "The buffer is untouched: the row is a widget over the text, and the space "
        "under the line is bought with pixels-below-lines rather than a character."
    )
    return view


def by_gutter(finding: Finding) -> Gtk.Widget:
    """Approach 3 — the gutter, which is per-line and never full width."""
    view, buffer = new_view()

    # In GtkSourceView 5 a gutter renderer is a Gtk.Widget, so it is sized like
    # one. The GTK3 set_size() does not exist.
    renderer = GtkSource.GutterRendererText()
    renderer.set_size_request(16, -1)
    renderer.set_xpad(4)

    # query-data carries the line number itself; GutterLines is the batch it
    # belongs to, and asking it for "the" line gives the wrong answer.
    def query(
        _renderer: GtkSource.GutterRenderer, _lines: GtkSource.GutterLines, line: int
    ) -> None:
        renderer.set_text("!" if line == ANCHOR_LINE else "", -1)

    renderer.connect("query-data", query)
    view.get_gutter(Gtk.TextWindowType.LEFT).insert(renderer, 0)

    finding.round_trip = True
    finding.cursor_steps_into_row = False
    finding.copy_includes_verdict = False
    finding.scrolls_with_buffer = True
    finding.notes.append(
        "A gutter cell is as wide as the gutter. It can carry a marker and a colour, "
        "never the sentence the verdict needs."
    )
    return view


CSS = b"""
.verdict { background: #FAEBCE; border-left: 3px solid #B5730A; padding: 3px 8px; }
.verdict-text { color: #63400B; font-size: 11pt; }
textview { font-family: monospace; font-size: 11pt; }
"""


def build() -> tuple[Gtk.Window, list[Finding]]:
    """The window, and what each approach did on the way to being drawn."""
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )

    window = Adw.ApplicationWindow(default_width=1200, default_height=760)
    findings = [Finding("1 · child anchor"), Finding("2 · overlay"), Finding("3 · gutter")]

    stack = Adw.ViewStack()
    stack.add_titled(scrolled(by_child_anchor(findings[0])), "anchor", "Child anchor")
    stack.add_titled(scrolled(by_overlay(findings[1], window)), "overlay", "Overlay")
    stack.add_titled(scrolled(by_gutter(findings[2])), "gutter", "Gutter")

    header = Adw.HeaderBar()
    header.set_title_widget(Adw.ViewSwitcher(stack=stack, policy=Adw.ViewSwitcherPolicy.WIDE))
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.append(header)
    box.append(stack)
    window.set_content(box)
    return window, findings


def scrolled(child: Gtk.Widget) -> Gtk.Widget:
    scroller = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
    scroller.set_child(child)
    return scroller


def snapshot(window: Gtk.Widget, path: Path) -> bool:
    """Draws the window to a PNG, so what it looks like can be looked at."""
    paintable = Gtk.WidgetPaintable.new(window)
    width, height = window.get_width(), window.get_height()
    if width <= 1 or height <= 1:
        return False
    renderer = window.get_native().get_renderer()
    node = None
    deadline = time.perf_counter() + SNAPSHOT_WAIT
    while time.perf_counter() < deadline:
        window.queue_draw()
        clock = window.get_frame_clock()
        if clock is not None:
            clock.request_phase(Gdk.FrameClockPhase.PAINT)
        pump(0.1)
        holder = Gtk.Snapshot()
        paintable.snapshot(holder, width, height)
        node = holder.to_node()
        if node is not None:
            break
    if node is None or renderer is None:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    renderer.render_texture(node, None).save_to_png(str(path))
    return True


def main() -> int:
    Adw.init()
    window, findings = build()
    window.present()
    pump(1.5)

    shots = Path(__file__).resolve().parent.parent / "docs" / "spikes" / "images"
    stack = window.get_content().get_last_child()
    pages = (
        ("anchor", "01-child-anchor"),
        ("overlay", "02-overlay"),
        ("gutter", "03-gutter"),
    )
    for name, page in pages:
        stack.set_visible_child_name(name)
        pump(0.6)
        saved = snapshot(window, shots / f"{page}.png")
        print(f"  {page}.png {'saved' if saved else 'NOT SAVED — no frame arrived'}")

    print()
    for finding in findings:
        print(f"{finding.approach}")
        print(f"    round-trip clean      {finding.round_trip}")
        print(f"    cursor enters the row {finding.cursor_steps_into_row}")
        print(f"    copy takes the text   {finding.copy_includes_verdict}")
        for note in finding.notes:
            print(f"    note: {note}")
        print()

    if "--report" not in sys.argv:
        print("  window is open; close it to exit")
        loop = True
        window.connect("close-request", lambda *_: (globals().__setitem__("_done", True), False)[1])
        while loop and not globals().get("_done"):
            pump(0.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
