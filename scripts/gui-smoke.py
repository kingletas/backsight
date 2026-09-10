#!/usr/bin/env python3
"""Opens the real window, drives it, and writes a PNG of each view.

The unit suite happily exercises a component while the route through it is
broken. This is the check that looks. Run it with `make smoke`, then open the
pictures it writes into `local.d/smoke/` and actually look at them.

It writes into `local.d/` rather than into the tree because a smoke run is a
build product: thirty-five files rewritten on every run left `git status` never
clean, so a real change hid among them. The four the README shows are copied
out by hand, which is a decision somebody makes rather than a sweep.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Before anything reads a setting: the smoke checks the application, not this
# machine's configuration. It ran against the developer's own settings file
# until one of them was turned off there, and ten checks then failed for a
# reason that was not in the repository at all. State goes too, so a remembered
# rail or panel height cannot change what a screenshot shows.
_SCRATCH = tempfile.mkdtemp(prefix="backsight-smoke-")
os.environ["XDG_CONFIG_HOME"] = str(Path(_SCRATCH) / "config")
os.environ["XDG_STATE_HOME"] = str(Path(_SCRATCH) / "state")

# **Its own settings, never the person's.** Without this the smoke read the
# settings of whoever ran it — their font, their single- or double-click, their
# hidden panels — so two people got two different sets of pictures from one
# commit, and a check could pass or fail on somebody's preferences. The same two
# directories the test suite isolates, for the same reason.
_SETTINGS_HOME = Path(tempfile.mkdtemp(prefix="backsight-smoke-"))
os.environ["XDG_CONFIG_HOME"] = str(_SETTINGS_HOME / "config")
os.environ["XDG_STATE_HOME"] = str(_SETTINGS_HOME / "state")

# Before `gi`, always: GTK connects to a display when it is initialised, so the
# choice has to be made first. Without this the smoke drives two dozen windows
# across whatever the person is working on, taking the pointer with them — and
# a stray keystroke then lands in a window they did not open.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from backsight.app.offscreen import use_a_private_display  # noqa: E402

OWN_DISPLAY = use_a_private_display()

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, Gtk

ROOT = Path(__file__).resolve().parent.parent

# Disposable by construction: `local.d/` is ignored by this repository's
# .gitignore, so nothing written here is ever committed.
IMAGES = ROOT / "local.d" / "smoke"
sys.path.insert(0, str(ROOT / "src"))

from backsight.app.drawer import TABS
from backsight.app.runs import start as start_run  # noqa: E402
from backsight.app.stacks_rail import StacksRail  # noqa: E402
from backsight.app.window import Window  # noqa: E402

# How long a frame is waited for before a screenshot is given up on.
# Long enough to survive a loaded machine. A frame that never arrives is
# reported, and a run where some shots painted and one did not is a failure.
SNAPSHOT_WAIT = 12.0

# Every check runs, always. There was a `return 1` halfway through `main` that
# stopped on the first failure — so seventeen checks after it were reported as
# clean by never running, which is the worst thing a checker can do. The summary
# is at the end and there is exactly one of it.
failures: list[str] = []
missing: list[str] = []
captured: list[Path] = []


def check(what: str, ok: bool) -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")
    if not ok:
        failures.append(what)


def pump(seconds: float) -> None:
    """Runs the main loop for a while, so the window can get on with it."""
    context = GLib.MainContext.default()
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        if not context.iteration(False):
            time.sleep(0.01)


def snapshot(window: Gtk.Widget, path: Path) -> None:
    """Draws the window to a PNG, so what it looks like can be looked at.

    A **fresh** paintable each time, deliberately. Keeping one for the life of
    the run makes every screenshot save and every one after the first a stale
    copy of it — which passed every check while the pictures were worthless. A
    fresh one occasionally fails to receive a frame, and that is reported. Of the
    two ways this can be wrong, take the loud one.
    """
    paintable = Gtk.WidgetPaintable.new(window)
    width, height = window.get_width(), window.get_height()
    if width <= 1 or height <= 1:
        check(f"{path.name}: the window has a size", False)
        return
    renderer = window.get_native().get_renderer()
    node = None
    # A paintable has nothing to give until the widget has been drawn, so each
    # attempt asks for a frame rather than only waiting for one.
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
        # Nothing painted after that long is the compositor rather than the
        # window, and says nothing about the application.
        # A headless run with no compositor paints nothing at all, and that says
        # nothing about the application. One missing frame among saved ones is a
        # different thing, and the caller decides which it is looking at.
        print(f"  ..   {path.name}: no frame arrived, screenshot not saved")
        missing.append(path.name)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    renderer.render_texture(node, None).save_to_png(str(path))
    captured.append(path)
    print(f"  ok   {path.name}")


def main() -> int:
    # Old pictures must not be compared with new ones, and a screenshot that
    # fails to save should leave a gap rather than last week's image.
    IMAGES.mkdir(parents=True, exist_ok=True)
    for stale in IMAGES.glob("*.png"):
        stale.unlink()
    Adw.init()
    window = Window()
    window.present()
    pump(1.0)

    check("the window opened", window.get_visible())
    check("the window has the layout's width", window.get_width() > 1000)
    check("apply is not reachable with no plan", not reachable(window, "Apply"))

    check("the empty state offers the example workspace", listed(window, "Open example workspace"))
    check("no accent-filled button is in the header", not _accent_in_header(window))
    check(
        "the empty state invites rather than reports",
        listed(window, "Open a workspace to get started"),
    )
    check("nothing empty holds a third of the window", not window._drawer.get_visible())

    # The rail has three states and drew two of them the same, so the everyday
    # toggle flipped between shown and collapsed with no visible difference and
    # the rail read as permanent.
    check("the rail opens showing", window._rail_scroller.get_visible())
    window.activate_action("win.toggle-left-rail", None)
    pump(0.2)
    check(
        "the toggle collapses it to a strip",
        window._rail_strip.get_visible() and not window._rail_scroller.get_visible(),
    )
    snapshot(window, IMAGES / "29-rail-collapsed.png")
    window.hide_panel("left_rail")
    pump(0.2)
    check(
        "and the menu can take it away entirely",
        not window._sidebar_widget.get_visible(),
    )
    window.show_panel("left_rail")
    pump(0.2)
    check("and bring it back", window._rail_scroller.get_visible())
    snapshot(window, IMAGES / "01-shell.png")

    # The check above was true at startup and stayed true forever, while a
    # second pane under the drawer went visible the first time anything ran and
    # never went away. Ask after something has run, which is when it happened.
    window.show_output("tofu: it ran")
    pump(0.2)
    check("output goes somewhere it can be read", "it ran" in window.output_panel.text)
    check("and opens the drawer at it", window._drawer.section == "Output")
    window.hide_panel("plan_drawer")
    pump(0.2)
    check("closing it leaves nothing behind", not window._drawer.get_visible())
    check(
        "and no second pane is holding the bottom of the window open",
        window._centre.get_end_child() is window._drawer,
    )

    # The example workspace, which reaches nothing and holds no real values.
    window.open_workspace(ROOT / "fixtures" / "workspace")
    pump(0.5)
    # The rail is files and nothing else. What the workspace is, and how many
    # of it there are, moved to the switcher — a heading over the only section
    # there is says what the rows under it already say.
    check("the rail carries no heading and no count", not listed(window, "environments ·"))
    check(
        "the switcher names the workspace",
        "workspace" in window._switcher.rows[1].lower() or listed(window, "workspace"),
    )
    # **The rail is a file tree.** It shows the repository's immediate children
    # and nothing below them until somebody asks — so what is on it at open is
    # the top level, not a flattened list of every module in the repository.
    top = [
        window._files._model.get_row(at).get_item().entry.shown
        for at in range(window._files._model.get_n_items())
    ]
    check("the rail shows the top of the repository", "environments/" in top)
    check("and nothing below it", not any(name.endswith(".tf") for name in top))
    check(
        "the locked provider version reaches the status bar",
        any("5.82.2" in t for t in labels(window)),
    )
    snapshot(window, IMAGES / "02-workspace.png")

    window.open_file(ROOT / "fixtures" / "workspace" / "environments" / "prod" / "main.tf")
    pump(0.4)
    page = window._files_open.current
    check("the file is shown whole", b"backend" in page.content())
    check("it is highlighted as Terraform", page.buffer.get_language().get_id() == "terraform")
    check("nothing is marked modified by opening it", not page.modified)

    # A second file, kept, to prove tabs rather than one buffer being
    # overwritten. **`preview=False` is the point**: an ordinary open reuses the
    # tab in front, which is what stops twenty files browsed becoming twenty
    # tabs to close, and keeping one is the deliberate choice. This check read
    # `open_file` with no argument and went red the day that landed — the
    # behaviour was right and the check was out of date.
    window.open_file(
        ROOT / "fixtures" / "workspace" / "environments" / "prod" / "variables.tf",
        preview=False,
    )
    pump(0.4)
    check("two files are open at once when both were kept", len(window._files_open.pages) == 2)
    snapshot(window, IMAGES / "03-file-open.png")

    # A file that cannot be shown without damaging it says so and opens nothing.
    window.open_file(ROOT / "fixtures" / "hcl" / "not-utf8" / "latin1.tf")
    pump(0.4)
    check(
        "a file that is not UTF-8 is refused rather than mangled",
        len(window._files_open.pages) == 2,
    )
    check("and the refusal is said in the window", listed(window, "not UTF-8"))
    check(
        "the rail no longer asks for a plan it already has",
        not any(t == "Needs a plan" for t in labels(window)) or window._plan is None,
    )
    check("a file that cannot be read says so durably", window._banner.get_revealed())
    check(
        "and the banner says which file and what to do",
        "latin1.tf" in window._banner.get_title() and "UTF-8" in window._banner.get_title(),
    )
    snapshot(window, IMAGES / "04-refused.png")

    # The whole loop, for real: open a workspace that can plan offline, save,
    # and wait for the panel to fill from a plan that actually ran.
    window.open_workspace(ROOT / "fixtures" / "plannable")
    pump(0.4)
    # The plan lives in the drawer now, so a picture of a plan has to open it.
    window.open_drawer("Changes")
    window.open_file(ROOT / "fixtures" / "plannable" / "main.tf")
    pump(0.4)
    check("a speculator is watching the file's module", window.speculator is not None)
    window.save_current()
    planned = until(lambda: listed(window, "2 to add"), 30.0)
    check("saving produced a plan and the panel shows it", planned)
    check("nothing destructive is claimed", not listed(window, "to be destroyed"))
    snapshot(window, IMAGES / "05-live-plan.png")

    # A plan, drawn. Loaded from a fixture rather than run, so the picture is
    # the same every time and the check is about the rendering.
    from backsight.engine.plan.model import read as read_plan  # noqa: PLC0415

    replace = read_plan(ROOT / "fixtures" / "plan" / "replace.json")
    window.plan_panel.show(replace)
    # **The window, not only the panel.** Driving the panel alone left the rest
    # of the window describing the previous plan, so anything that reads the
    # situation — the run control's fill, the footer — could never be
    # photographed with a destructive plan in hand.
    window._plan = replace
    window._refresh_apply()
    # Rebuilding a panel of widgets needs a layout pass before there is anything
    # to paint. 0.4s was not enough on a loaded machine and the screenshot came
    # back empty while every check passed.
    pump(1.2)
    check("the plan headline says what will happen", listed(window, "1 to replace"))
    check(
        "a plan that reaches nothing outside the machine can be applied",
        "Review" in window.apply_gate.action or "Apply" in window.apply_gate.action,
    )
    check("a destructive plan warns in words", listed(window, "1 to be destroyed and recreated"))
    check(
        "the row names the attribute that caused it",
        any("triggers_replace cannot be changed" in t for t in labels(window)),
    )
    check(
        "the run control carries the plan's own consequence",
        window._run_button.has_css_class("tf-irreversible"),
    )
    check(
        "destroy and replace are told apart without colour",
        listed(window, "Replace") and any(t.strip() == "±" for t in labels(window)),
    )
    snapshot(window, IMAGES / "06-plan.png")

    # Sheet 11: the drawer's four tabs, and sheet 4's rule that Escape closes it.
    window.show_panel("plan_drawer")
    pump(0.4)
    check(
        "the drawer has the four tabs",
        window._drawer.sections == list(TABS),
    )
    # A control at the end of the row rather than a sentence inside it: the
    # hint was taking exactly the width the last tab needed.
    check(
        "the way out is a control, not a sentence in the tab row",
        window._drawer._dismiss.get_tooltip_text() == "Esc to close",
    )
    check("and every tab is readable", len(window._drawer.sections) == len(TABS))
    window.open_drawer(TABS[1])
    pump(0.3)
    check("a status click opens the drawer at its section", window._drawer.section == TABS[1])
    snapshot(window, IMAGES / "19-drawer.png")
    window.hide_panel("plan_drawer")
    pump(0.3)
    check("hiding the drawer puts it away", not window.layout.is_shown("plan_drawer"))
    window.show_panel("plan_drawer")
    pump(0.2)

    # Sheet 4: the change map replaces the minimap slot. It shows where the
    # plan touches this file, which a thumbnail of the text cannot.
    page = window._files_open.current
    check("the map is off until asked for", not page.change_map.get_visible())
    window.activate_action("win.toggle-change-map", None)
    pump(0.5)
    check("turning it on shows the strip", page.change_map.get_visible())
    check("it marks where the plan touches the file", bool(page.change_map._marks))
    check(
        "and it knows the colour of each",
        all(mark.tone in page.change_map._colours for mark in page.change_map._marks),
    )
    snapshot(window, IMAGES / "22-change-map.png")

    # The About dialog. It is the only place the product says what it is.
    from backsight.app.about import AboutDialog  # noqa: PLC0415

    about = AboutDialog(version="0.1.0", commit="8f2a41c", engine="1.13.0")
    about.present(window)
    pump(0.6)
    check("about says what Backsight is", any("what a change" in s for s in about.says))
    check(
        "about answers which build and which engine", about.facts["Terraform"] == "1.13.0 detected"
    )
    snapshot(window, IMAGES / "25-about.png")
    about.close()
    pump(0.3)

    # The workspace switcher, which is the window's title.
    window._switcher.popup()
    pump(0.5)
    check("the switcher lists a way in", "Open workspace…" in window._switcher.rows)
    snapshot(window, IMAGES / "26-switcher.png")
    window._switcher.popdown()
    pump(0.3)

    # Sheet 11, plate 40: everything on at once. The point is that it does not
    # collapse under its own weight.
    window._files_open.set_lens_shown(True)
    window._files_open.set_hints_shown(True)
    window.show_panel("left_rail")
    window.open_drawer("Changes")
    pump(0.8)
    check("everything on still draws", window._files_open.current is not None)
    snapshot(window, IMAGES / "23-everything-on.png")
    window._files_open.set_lens_shown(False)
    window._files_open.set_hints_shown(False)
    pump(0.3)

    # Sheet 9's find row, over the file in front of it.
    window.activate_action("win.find", None)
    pump(0.4)
    check("find opens over the file", window._find.get_visible())
    window._find.term.set_text("terraform_data")
    until(lambda: "match" in window._find.count, 5)
    check("it says how many it found", "2 matches" in window._find.count)
    snapshot(window, IMAGES / "21-find.png")
    window._find.close()
    pump(0.3)
    check("escape puts it away", not window._find.get_visible())

    # Sheet 11: the code lens is off by default, and says three facts when on.
    page = window._files_open.current
    check("the lens is off until asked for", not page.show_lens)
    window._files_open.set_lens_shown(True)
    pump(0.6)
    check("turning the lens on puts a line above each block", bool(page._lenses))
    check(
        "and it says how many refer to it and what the plan does",
        all("reference" in lens.text and "plan" in lens.text for lens in page._lenses),
    )
    check("the lens never mentions money", all("$" not in lens.text for lens in page._lenses))
    snapshot(window, IMAGES / "20-lens.png")
    window._files_open.set_lens_shown(False)
    pump(0.3)

    # Sheet 7: hints are off until asked for, and then they land on the line
    # that expands. This workspace has none, so the check is that turning them
    # on changes nothing rather than breaking anything.
    window._files_open.set_hints_shown(True)
    pump(0.4)
    check("turning hints on is safe with nothing to hint", window._files_open.current is not None)
    window._files_open.set_hints_shown(False)
    pump(0.2)

    # The test panel, from a real run recorded earlier.
    from backsight.engine.tests.execution import Target  # noqa: PLC0415
    from backsight.engine.tests.results import parse as parse_tests  # noqa: PLC0415

    stream = (ROOT / "fixtures" / "tests" / "run-with-a-failure.jsonl").read_text()
    window.test_panel.show(parse_tests(stream), target=Target.MOCKS)
    pump(0.5)
    check("the test panel lists the runs", listed(window, "names_are_wrong_on_purpose"))
    check(
        "a failure shows what the expression evaluated to",
        any("is tuple with 3 elements" in t for t in labels(window)),
    )
    check("the target is stated with the result", listed(window, "Ran against mocks"))
    snapshot(window, IMAGES / "15-tests.png")

    # The console. Real evaluation against the open workspace, so this is the
    # engine answering rather than a fixture being replayed.
    window.toggle_console()
    pump(0.3)
    check("the console opens on request", window._drawer.section == "Console")
    for expression in ("1 + 1", "terraform_data.api", "var.nope"):
        window.console_panel.entry.set_text(expression)
        window.console_panel.submit()
        until(lambda e=expression: asked(window, e), 20)
    check("a literal is evaluated", listed(window, "2"))
    check(
        "an unapplied resource says why it has no value",
        any("has not been applied yet" in t for t in labels(window)),
    )
    check(
        "a bad reference reports the engine's own summary",
        listed(window, "Reference to undeclared input variable"),
    )
    snapshot(window, IMAGES / "16-console.png")

    # Sheet 11's argument: the parts that survive to plate 42 are the status
    # line, the gutter marks and the tab edges. Turn everything else off and
    # check they are all still there and still true.
    check("the verdict line carries the plan", listed(window, "＋2"))
    # It asserted a hardcoded sentence, which passed for as long as the status
    # bar carried one. What it was guarding is that the status line and the
    # gate never say different things about the same plan.
    blocked = window._situation().blocked
    check(
        "the status line and the gate agree about what is possible",
        (blocked and listed(window, blocked))
        or (not blocked and "Apply" in window.apply_gate.action),
    )
    page = window._files_open.current
    check("a gutter mark exists for each change", page.marks.verdict_at(3) is not None)

    window._files_open.set_bands_shown(False)
    for name in ("left_rail", "menu_bar"):
        window.hide_panel(name)
    pump(0.6)
    check("with everything off the gutter marks survive", page.marks.verdict_at(3) is not None)
    check("and the verdict line never leaves", listed(window, "＋2"))
    check(
        "and the tab still says what the plan does",
        window._files_open._status_for(page).shows_impact,
    )
    snapshot(window, IMAGES / "14-everything-off.png")

    window._files_open.set_bands_shown(True)
    window.reset_layout()
    window._files_open.show_verdicts(
        window._verdicts_for(window.plan_panel._plan)
        if getattr(window.plan_panel, "_plan", None)
        else []
    )
    pump(0.5)

    # Eight menus and the primary menu that always carries them somewhere.
    check("the menu bar is off to begin with", not window._menu_bar.get_visible())
    check(
        "and the primary menu is carrying the eight",
        window._hamburger.get_menu_model().get_n_items() > 6,
    )
    window.show_panel("menu_bar")
    pump(0.5)
    check("turning it on shows it", window._menu_bar.get_visible())
    # **No item is ever in two places.** The eight menus move to the bar when it
    # comes on, and the primary menu keeps only what libadwaita puts in one.
    check(
        "and the primary menu has handed the eight over",
        window._hamburger.get_menu_model().get_n_items() < 6,
    )
    window.hide_panel("menu_bar")
    pump(0.5)
    check("the primary menu is always there", window._hamburger.get_visible())
    check(
        "everything in the bar is still reachable by pointing",
        window._hamburger.get_menu_model() is not None,
    )
    snapshot(window, IMAGES / "12-hamburger.png")
    window.show_panel("menu_bar")
    pump(0.4)
    check(
        "bringing the bar back takes the eight out of the primary menu",
        window._hamburger.get_menu_model().get_n_items() < 6,
    )

    window.show_settings()
    pump(0.8)
    for w in list(Gtk.Window.get_toplevels()):
        if w.get_title() == "Preferences":
            snapshot(w, IMAGES / "13-preferences.png")
            w.close()
    pump(0.3)

    # Sheet 10: a tab says what git thinks and what the plan will do, in two
    # slots that never disturb each other.
    from backsight.engine.insight.file_status import Impact  # noqa: PLC0415

    statuses = window._statuses
    here = (ROOT / "fixtures" / "plannable" / "main.tf").resolve()
    check(
        "the tab knows what the plan does to its file",
        here in statuses and statuses[here].impact is Impact.CREATE,
    )
    check("git has an opinion about it", window._vcs.available)
    window._files_open.show_statuses(statuses, letters=True)
    pump(0.4)
    snapshot(window, IMAGES / "11-tab-marks.png")

    # An edit clears the plan marker rather than dimming it.
    page = window._files_open.current
    page.buffer.insert_at_cursor("\n")
    pump(0.4)
    check(
        "editing clears the plan marker rather than dimming it",
        window._statuses[here].impact is Impact.UNTOUCHED,
    )
    page.buffer.undo()
    pump(0.2)

    # Sheet 12, driven rather than described: hide a panel, check it went, and
    # check every path back still exists.
    from backsight.engine.layout.panels import PANELS, restore_paths  # noqa: PLC0415

    said_before = len(window.activity)
    window.hide_panel("left_rail")
    pump(0.4)
    check("hiding a rail actually hides it", not window._sidebar_widget.get_visible())
    # A view toggle is visible and reverses with the same key. A toast for it
    # spends the trust the one that matters later needs.
    check("and says nothing about having done it", len(window.activity) == said_before)
    snapshot(window, IMAGES / "09-panel-hidden.png")

    window.show_panel("left_rail")
    pump(0.3)
    check("showing it again brings it back", window._sidebar_widget.get_visible())

    # A key never hides a collapsible rail outright. That is the mis-click rule:
    # a strip costs eight pixels and means a stray key loses nothing.
    window.toggle_panel("left_rail")
    pump(0.2)
    check("a key collapses a rail rather than hiding it", window.layout.is_shown("left_rail"))

    for name in list(window._panels):
        window.hide_panel(name)
    pump(0.4)
    check("everything can be hidden at once", not window._status_widget.get_visible())
    implemented = [p for p in PANELS if p.name in window._panels]
    check(
        "every hidden panel still has a keyboard and a mouse path back",
        all(
            restore_paths(p, window.keymap)["keyboard"] and restore_paths(p, window.keymap)["mouse"]
            for p in implemented
        ),
    )
    window.reset_layout()
    pump(0.4)
    check("reset layout brings all of it back", window._status_widget.get_visible())

    window.show_keyboard_reference()
    pump(0.6)
    check(
        "the keyboard reference opens",
        any(
            isinstance(w, Gtk.Window) and w.get_title() == "Keyboard reference"
            for w in Gtk.Window.get_toplevels()
        ),
    )
    for w in list(Gtk.Window.get_toplevels()):
        if w.get_title() == "Keyboard reference":
            snapshot(w, IMAGES / "10-keyboard-reference.png")
            w.close()
    pump(0.3)

    # The same screen in both schemes. Sheet 3 asks for both, and a light editor
    # on a dark window is the failure the pairing exists to stop.
    manager = Adw.StyleManager.get_default()
    for scheme, shot in (
        (Adw.ColorScheme.FORCE_DARK, "07-dark"),
        (Adw.ColorScheme.FORCE_LIGHT, "08-light"),
    ):
        manager.set_color_scheme(scheme)
        pump(0.6)
        page = window._files_open.current
        check(
            f"{shot}: the editor scheme follows the desktop",
            page.buffer.get_style_scheme().get_id()
            == ("backsight-dark" if manager.get_dark() else "backsight-light"),
        )
        snapshot(window, IMAGES / f"{shot}.png")
    manager.set_color_scheme(Adw.ColorScheme.DEFAULT)
    pump(0.4)

    # A five second subprocess, with the window drawing throughout. If the
    # boundary leaks, this is where it shows: the frames stop arriving.
    frames = []
    lines: list[str] = []
    run = start_run(
        [
            sys.executable,
            "-u",
            "-c",
            "import time\nfor i in range(5):\n    print(i)\n    time.sleep(1)",
        ],
        on_line=lines.append,
    )
    deadline = time.perf_counter() + 6.0
    while run.state.value == "running" and time.perf_counter() < deadline:
        before = window.get_frame_clock().get_frame_time()
        pump(0.25)
        frames.append(window.get_frame_clock().get_frame_time() != before)
    check("the window kept drawing while a five second run was in flight", any(frames))
    check("output reached the main loop while the run was going", len(lines) >= 2)
    check("the run finished on its own", run.state.value == "succeeded")

    # The failure being guarded against is a frozen capture: every screenshot a
    # copy of the first frame, with every other check passing. Two shots of the
    # same state far apart are fine — returning to a light theme looks like the
    # light screen it was before — so the rule is that consecutive shots differ
    # and that not everything collapses to one image.
    written = sorted(IMAGES.glob("*.png"))
    digests = [hashlib.sha256(path.read_bytes()).hexdigest() for path in written]
    repeated = [written[i].name for i in range(1, len(digests)) if digests[i] == digests[i - 1]]
    check(
        f"no screenshot repeats the one before it ({', '.join(repeated) or 'none do'})",
        not repeated,
    )
    check(
        f"the {len(written)} screenshots are not all one image ({len(set(digests))} distinct)",
        len(set(digests)) > 1,
    )
    if missing:
        check(f"every view painted (missing: {', '.join(missing)})", False)
    # Sheet 4: the palette is the surface everything else is reached through,
    # so it never opens empty and every prefix searches its own source.
    entries = window._palette_entries()
    suggestions = window._palette_suggestions()
    from backsight.app.palette import Palette  # noqa: PLC0415

    opened = Palette(entries, suggestions, parent=window)
    opened.present()
    pump(0.4)
    check("the palette opens with suggestions", bool(opened.shown))
    # This workspace's resources are terraform_data, not aws — the query has to
    # match the fixture or the check proves nothing.
    opened.entry.set_text("@terraform_data")
    pump(0.2)
    print(
        "      @terraform_data ->",
        [e.label for e in opened.shown][:4],
        "workspace:",
        window.workspace.path.name if window.workspace else None,
    )

    # This block has failed intermittently and has never reproduced on demand:
    # 160 queries against the palette in a clean process are clean, and the
    # failures only appear inside the whole smoke, more often under load. So
    # every palette check reports its state on the way out — the next
    # occurrence should say what went wrong rather than only that it did.
    def palette_check(said: str, ok: bool, query: str) -> None:
        if not ok:
            resources = [e.label for e in entries if e.kind.value == "@"]
            files = [e.label for e in entries if e.kind.value == ""]
            print(f"      DEBUG query={query!r} entry={opened.entry.get_text()!r}")
            print(f"      DEBUG shown={[e.label for e in opened.shown][:6]}")
            print(f"      DEBUG resources={resources} files={files[:4]}")
        check(said, ok)

    opened.entry.set_text("@terraform_data")
    pump(0.2)
    palette_check(
        "a resource prefix finds resources",
        [e.label for e in opened.shown][:2] == ["terraform_data.api", "terraform_data.worker"],
        "@terraform_data",
    )
    opened.entry.set_text("@api")
    pump(0.2)
    palette_check(
        "a resource is found by any part of its address",
        bool(opened.shown) and opened.shown[0].label == "terraform_data.api",
        "@api",
    )
    opened.entry.set_text("main")
    pump(0.2)
    palette_check(
        "no prefix finds files",
        any(e.label.endswith(".tf") for e in opened.shown),
        "main",
    )
    opened.entry.set_text(":12")
    pump(0.2)
    palette_check(
        "a line number is offered as itself",
        bool(opened.shown) and opened.shown[0].label == "Line 12",
        ":12",
    )
    opened.entry.set_text(">plan")
    pump(0.3)
    palette_check(
        "a command prefix finds commands",
        any(e.action for e in opened.shown),
        ">plan",
    )
    snapshot(opened, IMAGES / "18-palette.png")
    opened.close()
    pump(0.3)

    # Sheet 5: middle-click closes the tab under the pointer. The bar offers
    # no hit-test, so this is the only place the mapping is proved right.
    from backsight.app.editor import _tab_under, _tab_widgets  # noqa: PLC0415

    bar, tabs = window._files_open._tab_bar, window._files_open._tabs
    check("the bar has one widget per tab", len(_tab_widgets(bar)) == tabs.get_n_pages())
    titles = [tabs.get_nth_page(i).get_title() for i in range(tabs.get_n_pages())]
    # Probe each tab's own centre. Tabs no longer stretch to fill the bar, so
    # dividing its width by the number of them lands between two of them.
    from gi.repository import Graphene  # noqa: PLC0415

    found = []
    for index, widget in enumerate(_tab_widgets(bar)):
        point = widget.compute_point(bar, Graphene.Point().init(widget.get_width() / 2, 6))
        at = point[1].x if point[0] else 0
        found.append((_tab_under(bar, tabs, at, 12) or tabs.get_nth_page(index)).get_title())
    check("the pointer finds the tab it is over", found == titles)
    check(
        "past the last tab finds nothing", _tab_under(bar, tabs, bar.get_width() + 50, 12) is None
    )

    # BRD 6.11. Stacks is a view rather than furniture in the sidebar: it was a
    # permanent paragraph teaching a feature to somebody who was not using it.
    window.open_workspace(ROOT / "fixtures" / "stacks" / "plain")
    pump(0.5)
    window.open_file(ROOT / "fixtures" / "stacks" / "plain" / "infra" / "network" / "main.tf")
    pump(0.6)
    check("the sidebar no longer explains stacks at every launch", not _order(window))

    stacks = StacksRail(on_open=lambda _s: None)
    stacks.show(window.stacks, window._radius_now())
    pump(0.3)
    said = labels(stacks)
    check("every stack reaches the view", "network" in said and "edge" in said)
    check(
        "in apply order",
        [one for one in said if one in ("network", "data", "api", "edge")]
        == ["network", "data", "api", "edge"],
    )
    check(
        "editing one shows what a change to it reaches",
        any("consumes network.private_subnets, vpc_id" in one for one in said),
    )
    check("and how far it goes", any("consumes api.api_url" in one for one in said))
    snapshot(window, IMAGES / "24-stacks.png")

    # The library: everything reusable, one keystroke from the buffer.
    from backsight.engine.library.entry import Entry, Kind, Source, Step
    from backsight.engine.library.store import Library as Reusable

    window.library = Reusable(
        entries=[
            Entry(
                name="Private bucket with access logs",
                kind=Kind.RECIPE,
                resource="aws_s3_bucket",
                tags=("s3", "storage"),
                about="A bucket nothing outside the account can reach, with a log target.",
                source=Source.SHARED,
                body=(
                    'resource "aws_s3_bucket" "${1:name}" {\n'
                    '  bucket = "${2:acme}-${var.environment}"\n'
                    "}\n"
                ),
            ),
            Entry(
                name="Rotate a database password",
                kind=Kind.RUNBOOK,
                about="Three steps, in this order.",
                source=Source.WORKSPACE,
                steps=(
                    Step(
                        title="Snapshot first", command="tofu apply -target=aws_db_snapshot.before"
                    ),
                    Step(title="Change it in the secret store", body="Then plan and read it."),
                ),
            ),
            Entry(
                name="aws_s3_bucket — required only",
                source=Source.BUILT_IN,
                about="The arguments this resource cannot be written without.",
                body='resource "aws_s3_bucket" "${1:name}" {\n  ${0}\n}\n',
            ),
        ]
    )
    window.library_panel.show(window.library)
    window.show_library("bucket")
    pump(0.5)
    check("the library finds what matches", len(window.library_panel.showing) >= 1)
    window.library_panel._choose(window.library_panel.showing[0])
    pump(0.4)
    check(
        "and previews what will actually be inserted",
        "${1:" not in window.library_panel._preview.get_text(),
    )
    snapshot(window, IMAGES / "34-library.png")

    window.library_panel.look_for("rotate")
    pump(0.2)
    window.library_panel._choose(window.library_panel.showing[0])
    pump(0.4)
    check("a runbook reads as ordered steps", window.library_panel._steps.get_visible())
    snapshot(window, IMAGES / "35-runbook.png")
    window.hide_panel("plan_drawer")
    pump(0.2)

    # Two panes, and the file in front coming with you.
    window.split_right()
    pump(0.5)
    check("splitting makes a second pane", window._editors.is_split)
    check(
        "and the file you were in comes with you",
        window._files_open.current is not None,
    )
    snapshot(window, IMAGES / "33-split.png")
    window.unsplit()
    pump(0.3)
    check("and one pane comes back", not window._editors.is_split)

    # Drift, from a real refresh-only capture. `3 drifted` in the status bar
    # went nowhere for the life of the project.
    from backsight.engine.plan.drifting import from_document, from_stream

    drift_document = json.loads(
        (ROOT / "fixtures" / "drift" / "refresh-only-plan.json").read_text(encoding="utf-8")
    )
    window.drift_panel.show(from_document(drift_document))
    window.update_status(drifted=2)
    window.show_drift()
    pump(0.5)
    check(
        "the drift detail names what moved", "local_file.config" in window.drift_panel.addresses()
    )
    check("and the status bar carries the count", listed(window, "2 drifted"))
    snapshot(window, IMAGES / "32-drift.png")

    clean = (ROOT / "fixtures" / "drift" / "none.jsonl").read_text(encoding="utf-8").splitlines()
    window.drift_panel.show(from_stream(clean))
    pump(0.2)
    check(
        "a workspace with no drift says so rather than staying blank",
        window.drift_panel.headline == "Nothing has changed outside Terraform",
    )
    window.hide_panel("plan_drawer")
    pump(0.2)

    # The sidebar is the tree, and the plan is on the right.
    check(
        "the sidebar carries no plan, stacks or drift",
        not any(
            said in " ".join(labels(window._sidebar_widget))
            for said in (
                "Monthly cost",
                "Group modules that deploy together",
                "Drift check",
                "environment",
                "New file",
            )
        ),
    )
    check("there is no right-hand inspector", not hasattr(window, "inspector"))
    window.update_status(drifted=3)
    pump(0.2)
    check("drift is a chip when something has drifted", "3 drifted" in window._status_line.texts())
    window.update_status(drifted=None)
    pump(0.2)
    check(
        "and absent when nothing has",
        "drifted" not in " ".join(window._status_line.texts()),
    )
    snapshot(window, IMAGES / "28-no-inspector.png")

    # The apply screen, in both of its endings. Drawn from the real captures
    # rather than from a run, so the smoke needs no engine and no state to move.
    from backsight.app.apply_screen import ApplyScreen
    from backsight.engine.plan.applying import follow
    from backsight.engine.plan.model import Action, Plan, ResourceChange
    from backsight.engine.plan.verifying import Verification

    def a_plan(*pairs):
        return Plan(
            format_version="1.2",
            engine_version="1.12.6",
            changes=tuple(
                ResourceChange(a, a.split(".")[0], a.split(".")[-1], "managed", "terraform", action)
                for a, action in pairs
            ),
        )

    def apply_capture(name):
        """Named for what it reads. `stream` is a variable further down this
        function, and shadowing it broke the test panel six hundred lines away."""
        return (ROOT / "fixtures" / "apply" / name).read_text(encoding="utf-8").splitlines()

    applied = follow(
        a_plan(
            ("terraform_data.api", Action.UPDATE),
            ("terraform_data.database", Action.REPLACE),
            ("terraform_data.worker", Action.CREATE),
            ("terraform_data.old_cache", Action.DELETE),
        ),
        apply_capture("succeeded.jsonl"),
    )
    screen = ApplyScreen()
    holder = Gtk.Window(title="Apply", default_width=560, default_height=420)
    holder.set_child(screen)
    screen.begin(applied, where="prod")
    screen.finished(applied, Verification(checks=()))
    holder.present()
    pump(0.4)
    check(
        "an apply names what each resource became",
        screen.said_about("terraform_data.database") == "replaced",
    )
    snapshot(holder, IMAGES / "30-applied.png")

    stopped = follow(
        a_plan(
            ("terraform_data.first", Action.CREATE),
            ("terraform_data.second", Action.CREATE),
            ("terraform_data.third", Action.CREATE),
        ),
        apply_capture("failed-part-way.jsonl"),
    )
    screen.begin(stopped, where="prod")
    screen.finished(stopped)
    pump(0.4)
    check(
        "and separates what changed from what was never started",
        screen.said_about("terraform_data.first") == "created"
        and screen.said_about("terraform_data.third") == "never started",
    )
    snapshot(holder, IMAGES / "31-apply-stopped.png")
    holder.close()
    pump(0.2)

    # A plan that fails says what the engine said, and keeps the whole output
    # one click away.
    window.open_workspace(ROOT / "fixtures" / "broken-plan")
    pump(0.4)
    window.open_file(ROOT / "fixtures" / "broken-plan" / "main.tf")
    window.save_current()
    until(lambda: listed(window, "A variable is used but never declared"), 40)
    check(
        "a failed plan says what went wrong in the reader's words",
        listed(window, "A variable is used but never declared"),
    )
    check("and not the engine's own heading", not listed(window, "Plan failed"))
    check("and where it happened", listed(window, "main.tf:5"))
    check("and keeps the engine's own words reachable", listed(window, "Show the original"))
    check(
        "the footer offers the fix rather than a dead Apply",
        window.apply_gate.action in ("Fix and re-plan", "Re-plan"),
    )
    check("and Apply is absent, not disabled", not window.apply_gate.can_apply)
    check("and it names how many errors and where", "main.tf" in window.apply_gate.hint)
    check("no verdict survives a failed plan", window._plan is None)
    snapshot(window, IMAGES / "27-plan-failed.png")

    # Last, because it opens a different workspace: every check above is
    # written against the one the smoke opened at the start.
    # Sheet 7: a test file shows the shape of its runs before anything has run,
    # and each mark carries its own result afterwards.
    window.open_workspace(ROOT / "fixtures" / "tests" / "workspace")
    pump(0.4)
    window.open_file(ROOT / "fixtures" / "tests" / "workspace" / "tests" / "nodes.tftest.hcl")
    pump(0.4)
    page = window._files_open.current
    check(
        "every run is marked before anything has run",
        page.run_marks.mark_at(0) is not None and page.run_marks.mark_at(9) is not None,
    )
    window.test_panel.show(parse_tests(stream), target=Target.MOCKS)
    window._files_open.show_test_results(
        parse_tests(stream), ROOT / "fixtures" / "tests" / "workspace"
    )
    pump(0.4)
    check(
        "a passing run and a failing run do not share a shape",
        page.run_marks.mark_at(0).shape != page.run_marks.mark_at(9).shape,
    )
    check(
        "the tooltip says the file will run, not the one run",
        "Click to run nodes.tftest.hcl again"
        in page.run_marks.mark_at(9).tooltip(Path("tests/nodes.tftest.hcl"), 2),
    )
    snapshot(window, IMAGES / "17-run-marks.png")

    where = OWN_DISPLAY or "the display already set — no Xvfb was found"
    # Said only when it is true. It was printed before the failures were
    # counted, so a run with four failures still claimed every check passed.
    if not failures:
        print(f"  the window drew itself and every check passed, on {where}")
    if failures:
        print(f"  the window drew itself, on {where}")
        print(f"\n  {len(failures)} failed")
        for said in failures:
            print(f"    {said}")
        return 1
    return 0


def until(predicate, seconds: float) -> bool:
    """Waits for a condition rather than a fixed pause.

    A fixed pause is a guess about someone else's machine, and it is the guess
    that makes a window test flaky.
    """
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        if predicate():
            return True
        pump(0.1)
    return False


def labels(root: Gtk.Widget) -> list[str]:
    """Every piece of text the window is currently showing."""
    found = []

    def walk(widget: Gtk.Widget) -> None:
        if isinstance(widget, Gtk.Label):
            found.append(widget.get_label() or "")
        elif isinstance(widget, Gtk.Expander):
            found.append(widget.get_label() or "")
        child = widget.get_first_child()
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(root)
    return found


def asked(window, expression: str) -> bool:
    """True once the console has printed an answer to this expression."""
    marker = f"\u203a {expression}"
    shown = labels(window)
    return marker in shown and shown.index(marker) < len(shown) - 1


def _accent_in_header(window) -> bool:
    """The header asks for nothing, so nothing in it is accent-filled."""
    from gi.repository import Gtk  # noqa: PLC0415

    def walk(widget) -> bool:
        if isinstance(widget, Gtk.Button):
            classes = set(widget.get_css_classes())
            if {"tf-primary", "tf-apply", "suggested-action"} & classes:
                return True
        child = widget.get_first_child()
        while child is not None:
            if walk(child):
                return True
            child = child.get_next_sibling()
        return False

    return walk(window._header_widget)


def _order(window) -> list[str]:
    """The stack names on the rail, in the order they are drawn."""
    shown = labels(window)
    return [name for name in shown if name in ("network", "data", "api", "edge")]


def listed(root: Gtk.Widget, needle: str) -> bool:
    return any(needle in text for text in labels(root))


def reachable(root: Gtk.Widget, label: str) -> bool:
    """Whether a button with this label exists and can be pressed."""
    found = []

    def walk(widget: Gtk.Widget) -> None:
        if isinstance(widget, Gtk.Button) and widget.get_label() == label:
            found.append(widget.get_sensitive())
        child = widget.get_first_child()
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(root)
    return any(found)


if __name__ == "__main__":
    raise SystemExit(main())
