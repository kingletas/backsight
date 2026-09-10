"""The workbench window: code in the middle, consequences to the right.

The layout is the one in the wireframe — header, sidebar, editor over output,
analysis panel, status bar. Nothing here is Terraform-aware yet, so every panel
shows what would fill it rather than a number standing in for one.
"""

from __future__ import annotations

import difflib
import json
import shutil
import sys
import tempfile
import threading
import time
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango

from backsight import __version__
from backsight.app import (
    chrome_menu,
    context_menu,
    docs_panel,
    editing,
    empty_state,
    file_tree,
    menu_bar,
    workspaces,
)
from backsight.app.about import AboutDialog
from backsight.app.apply_gate import ApplyGate
from backsight.app.apply_screen import ApplyWindow
from backsight.app.backend_dialog import BackendDialog
from backsight.app.console_panel import ConsolePanel
from backsight.app.cost_panel import CostPanel
from backsight.app.dismissable import dismissable, escape_closes
from backsight.app.docs_panel import DocsPanel
from backsight.app.drawer import Drawer
from backsight.app.drift_panel import DriftPanel
from backsight.app.editor import Editor
from backsight.app.exposure_panel import ExposurePanel
from backsight.app.file_tree import FileTree
from backsight.app.find_bar import FindBar
from backsight.app.git_panel import GitPanel
from backsight.app.keyboard_reference import KeyboardReference
from backsight.app.keyboard_reference import pretty as pretty_key
from backsight.app.leading import keep_the_row
from backsight.app.library_panel import LibraryPanel
from backsight.app.output_panel import OutputPanel
from backsight.app.palette import Palette
from backsight.app.plan_panel import PlanPanel
from backsight.app.runs import on_main_loop
from backsight.app.settings_dialog import SettingsDialog
from backsight.app.split import Split
from backsight.app.stacks_rail import StacksRail
from backsight.app.switcher import WorkspaceSwitcher
from backsight.app.tab_stops import Stops
from backsight.app.test_panel import TestPanel
from backsight.app.theme import Theme, tokens
from backsight.engine.catalog import modules as catalog_modules
from backsight.engine.console import evaluation as expression_console
from backsight.engine.credentials import activity, roles
from backsight.engine.credentials import profiles as credentials
from backsight.engine.hcl import navigation
from backsight.engine.hcl.document import Document, NotUtf8
from backsight.engine.insight import exposure, file_status
from backsight.engine.insight import hints as hint_source
from backsight.engine.insight import lens as lens_source
from backsight.engine.insight import sections as analysis_sections
from backsight.engine.insight import suppression as suppressions
from backsight.engine.insight.file_status import cleared_of_plan, for_files
from backsight.engine.insight.graph import project
from backsight.engine.insight.hover import hover_at
from backsight.engine.insight.sections import EXPOSURE
from backsight.engine.insight.source_map import SourceMap
from backsight.engine.insight.verdicts import for_plan
from backsight.engine.layout import blocking, remembered, session, tree
from backsight.engine.layout.menus import (
    EVERY_ENTRY_POINT,
    FILE_CONTEXT_MENU,
    FOLDER_CONTEXT_MENU,
    GUTTER_MENU,
    RUN_MENU,
)
from backsight.engine.layout.panels import Layout, Visibility
from backsight.engine.library import conventions, generated, placeholders
from backsight.engine.library import entry as library_entry
from backsight.engine.library import store as library_store
from backsight.engine.plan import applying, drifting, repair, verifying
from backsight.engine.plan import commands as engine_commands
from backsight.engine.plan import footer as footer_model
from backsight.engine.plan.execution import PlanOutcome
from backsight.engine.plan.speculation import Progress, Speculator, Stage
from backsight.engine.policy import cost
from backsight.engine.policy import findings as policy
from backsight.engine.presentation import clipboard as clipboard_history
from backsight.engine.presentation import palette as palette_source
from backsight.engine.presentation import snippets as snippet_library
from backsight.engine.presentation import status as status_line
from backsight.engine.refactor import extract as refactor_extract
from backsight.engine.refactor import gate as refactor_gate
from backsight.engine.refactor import rename as refactor_rename
from backsight.engine.runner.process import RunTimedOut, capture
from backsight.engine.sandbox import convergence as sandbox_convergence
from backsight.engine.sandbox import ministack, override, runtime
from backsight.engine.schema import documentation, latest
from backsight.engine.schema import index as schema_index
from backsight.engine.settings import panels, recents, writing
from backsight.engine.settings.keys import Keymap, Unbindable
from backsight.engine.settings.layers import load as load_settings
from backsight.engine.stacks import freshness
from backsight.engine.stacks import graph as stack_graph
from backsight.engine.stacks import model as stack_model
from backsight.engine.tests import execution as test_run
from backsight.engine.text import handling as text_handling
from backsight.engine.text import lines as text_lines
from backsight.engine.vcs import git, working
from backsight.engine.vcs import history as git_history
from backsight.engine.workspace import backend as backend_state
from backsight.engine.workspace import files as workspace_files
from backsight.engine.workspace import recovery, watching
from backsight.engine.workspace import search as workspace_search
from backsight.engine.workspace.discovery import Module, Workspace, discover

# What a new workspace settings file says. A file that exists and is empty
# teaches nothing; this one says what it is for and what may go in it.
WORKSPACE_SETTINGS = """# Backsight settings for this workspace.
# Commit this file to share conventions across a team.
# Anything set here wins over the user's own settings.

[terraform]
# binary = "tofu"
# plan_on_save = true
"""

# The demo workspace: it plans with no provider, no credentials and no network,
# so it is the shortest path from install to seeing the product work.
#
# It ships with state, so the first plan somebody ever runs here shows an add, a
# change, a replace and a destroy rather than an empty diff. The first thing a
# new person sees should be what this product is for.
EXAMPLE_WORKSPACE = next(
    (
        candidate
        for candidate in (
            Path(__file__).resolve().parents[3] / "fixtures" / "example",
            Path(__file__).resolve().parents[3] / "fixtures" / "plannable",
        )
        if candidate.is_dir()
    ),
    None,
)

# Which key opens the palette on which prefix. The table, and the reason
# nothing lives only in a menu.
# How a verdict-line segment is drawn. Four consequence levels and no fifth,
# plus the two that are not severities: a plain fact, and the accent, which
# marks something in flight rather than something risky.
TONE_CLASSES = {
    status_line.Tone.FACT: "tf-faint",
    status_line.Tone.BLOCKING: "tf-blocked",
    status_line.Tone.SAFE: "tf-safe",
    status_line.Tone.DISRUPTIVE: "tf-disruptive",
    status_line.Tone.IRREVERSIBLE: "tf-irreversible",
    status_line.Tone.ACCENT: "tf-accent",
}

# What the verdict line keeps for itself before the chips get any: its own
# margins, and the gap that stops a chip touching the file facts.
CHIP_MARGIN = 48
CHIP_GAP = 16

# How far back navigation history goes. Long enough to undo a chain of jumps,
# short enough that nobody is walking a session backwards one press at a time.
HISTORY = 50

# Three presets. **A preset is not a mode**: nothing records that one is in
# force, so touching a single panel afterwards simply leaves it behind — there
# is no state to get stuck in and nothing to escape from.
PRESETS = {
    "focus": {"left_rail": False, "plan_drawer": False, "status_bar": True},
    "work": {"left_rail": True, "plan_drawer": False, "status_bar": True},
    "review": {"left_rail": True, "plan_drawer": True, "status_bar": True},
}

CHANGELOG = Path(__file__).resolve().parents[3] / "CHANGELOG.md"

# The page almost no product writes. Everything in it is a decision that has
# already been made and written down somewhere — this is it said out loud, in
# one place, to the person who just pressed a key that did nothing.
LIMITS = """What Backsight will not do

Three things this toolkit cannot do, and saying so beats a key that goes quiet.

  Multiple cursors        GtkSourceView 5 has no API for a second cursor.
                          Select all occurrences and Rename resource do most
                          of what they are reached for.
  Column selection        The same API, and the same absence.
  Code folding            None at all — not a partial API, none. The gutter
                          keeps the twelve pixels folding would need, so the
                          day it arrives no file reflows.
  Indent guides           Also absent. One guide for the enclosing block is
                          what this design asked for and cannot draw.

Four things it refuses on purpose.

  It never stores, shows or logs a credential. It discovers what this machine
  can authenticate as and holds none of it, and there is no setting to change
  that.

  It never rewrites a file you did not ask it to. No reformatting on save, no
  reordering, no normalising — there is a test that asserts byte-identical
  round trips over a corpus of ugly HCL, and it does not get weakened.

  It never applies anything you have not reviewed. Apply runs the plan
  artifact, not the configuration, so what runs is what you read.

  It plans a module, never a file. Excluding one file would mean a partial
  plan shown as though it were the plan, which is the confident-but-wrong
  claim this application exists against.

Three things that are simply not built yet, and are named rather than hidden.

  Generating an import block. The id format is per resource type and the
  provider schema does not carry it, so the block would be a guess that fails
  at apply.

  Scaffolding from the catalog, and adding a module to a stack definition.
  Both are in the menus, both say why on the item itself.

  Applying a stack. Backsight computes the order; a person runs them one at a
  time. That is a decision, not an omission.
"""

REPORTING = """Report a problem

  https://github.com/backsight/backsight/issues

What to include, in this order:

  1. What you did, and what happened instead.
  2. Tools -> What the last apply printed, or the Console tab.
  3. Help -> About, which carries the version and the engine it found.

What never to include: anything from a state file, a variables file, or a
plan artifact. Those carry real values from your infrastructure, and an
issue is public.
"""

PREFIXES = {"palette": ">", "goto-file": "", "goto-resource": "@"}

# What the palette offers before anything is typed. A blank palette is a wall
# for anyone who writes Terraform monthly — FR-APP-11.
SUGGESTED_COMMANDS = ("plan", "rename-resource", "run-tests")

# The analysis panel's sections come from `insight.sections`, derived from one
# plan so the rail cannot contradict its own headline.


def section(described) -> tuple[Gtk.Widget, Gtk.Label]:
    """One block of the rail, and the line that explains it.

    The label is handed back so the line can be rewritten when the plan
    changes. A section built once and never updated is how the rail came to
    say "Needs a plan" underneath a plan.

    The title is the rail heading's, not this one's — two headings for one
    section is what the rail looked like before it could fold.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    box.set_margin_bottom(10)
    box.set_margin_start(12)
    box.set_margin_end(12)

    detail = Gtk.Label(label=described.detail, xalign=0.0, wrap=True)
    detail.add_css_class("tf-faint")
    detail.add_css_class("tf-small")
    detail.set_visible(bool(described.detail))
    box.append(detail)
    return box, detail


def _named(pages: list) -> str:
    """The files, by name, or a count once there are too many to read."""
    names = sorted(Path(page.path).name for page in pages)
    if len(names) > 3:
        return f"{len(names)} open files"
    return ", ".join(names)


def _deleted_underneath(pages: list) -> str:
    one = len(pages) == 1
    return (
        f"{_named(pages)} {'has' if one else 'have'} been deleted, "
        f"and {'is' if one else 'are'} still open here"
    )


def _changed_underneath(pages: list) -> str:
    return (
        f"{_named(pages)} changed on disk, and you have unsaved changes "
        f"{'in it' if len(pages) == 1 else 'in them'}"
    )


# What git says about a file, as a colour on the row's left edge. Two pixels,
# out of the way of the name — a letter in the same label as the plan count was
# a third thing to read on a row whose whole job is a filename.
VCS_CLASSES = {"M": "tf-git-changed", "A": "tf-git-added", "?": "tf-git-untracked"}


def _inside(path: Path, module: Path) -> bool:
    """Whether a file belongs to a module, without walking the tree twice."""
    try:
        Path(path).resolve().relative_to(Path(module).resolve())
    except ValueError:
        return False
    return True


def _writes(window, key: str):
    """A setting toggle bound to its own key, not to the loop's last one.

    A closure over a loop variable reads it when it fires, so five toggles built
    in a loop would all write whichever setting the loop ended on — and every
    one of them would appear to work, on the wrong row.
    """
    return lambda _on: window.toggle_view(key)


def _matched(found: int, revealed: int) -> str:
    """What a filter says about what it found. **What is shown, not what is hidden.**"""
    if not found:
        return "nothing matches"
    said = f"{found} file{'' if found == 1 else 's'}"
    return said if found <= revealed else f"{said} · showing {revealed}"


def _marked(name: str, spans) -> str:
    """A name with the letters the filter matched picked out.

    Marked rather than the row being reordered or the tree flattened: the point
    of filtering in place is that you can still see where a thing lives.
    """
    said = GLib.markup_escape_text(name)
    if not spans:
        return said
    out: list[str] = []
    at = 0
    for start, end in spans:
        out.append(GLib.markup_escape_text(name[at:start]))
        out.append(f"<b>{GLib.markup_escape_text(name[start:end])}</b>")
        at = end
    out.append(GLib.markup_escape_text(name[at:]))
    return "".join(out)


def _rail_markup(relative: str, shared: str, found) -> str:
    """A module's name, with whatever every other module shares made quiet.

    `envs/prod`, `envs/staging` and `envs/dev` differ in four characters, and
    those four were the quietest thing on each row until this. The trailing
    slash is the other half: `network` and `network.tf` were one glyph apart.
    """
    marks = found.marks.get(relative) if found is not None else None
    body = _marked(relative, marks)
    if shared and relative.startswith(shared):
        rest = _marked(relative[len(shared) :], _shifted(marks, len(shared)))
        body = f'<span alpha="55%">{GLib.markup_escape_text(shared)}</span>{rest}'
    return f"{body}/"


def _shifted(spans, by: int):
    """The same marks, counted from further along the name."""
    if not spans:
        return spans
    return tuple((max(0, start - by), max(0, end - by)) for start, end in spans if end > by)


def placeholder(title: str, detail: str) -> Gtk.Widget:
    """A pane with nothing in it yet, which says so rather than sitting blank.

    Quietly. An empty pane is the ordinary state of a workbench nobody has opened
    a workspace in, and a headline in the middle of it reads as an error.
    """
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.set_valign(Gtk.Align.CENTER)
    box.set_halign(Gtk.Align.CENTER)
    box.set_vexpand(True)

    heading = Gtk.Label(label=title)
    heading.add_css_class("tf-medium")
    heading.add_css_class("tf-faint")
    box.append(heading)

    body = Gtk.Label(label=detail, wrap=True, justify=Gtk.Justification.CENTER)
    body.add_css_class("tf-small")
    body.add_css_class("tf-faint")
    # A measure, so the sentence does not run to both edges of a narrow rail.
    body.set_max_width_chars(28)
    box.append(body)
    box.set_margin_start(12)
    box.set_margin_end(12)
    return box


class Window(Adw.ApplicationWindow):
    """The single window the application opens."""

    def __init__(self, **kwargs: object) -> None:
        # The window comes back the size it was. A size that suits a laptop is
        # wrong on the monitor at the desk, so this belongs to the machine
        # rather than to a workspace.
        self._geometry = session.read_geometry()
        self._outer: Gtk.Paned | None = None
        kwargs.setdefault("default_width", self._geometry.width)
        kwargs.setdefault("default_height", self._geometry.height)
        super().__init__(**kwargs)
        self.set_title("Backsight")
        if self._geometry.maximised:
            self.maximize()
        # Coming back to the window is when a branch switch or a `fmt` in a
        # terminal has just happened.
        self.connect("notify::is-active", self._came_back)

        # First, because everything built below asks it what things look like.
        # One provider for the whole application, so a colour has one home.
        self.theme = Theme.shared(self.get_display())

        self.workspace: Workspace | None = None
        self.speculator: Speculator | None = None
        self._overridden: dict[str, str | None] = {}
        self.keymap = Keymap.build()
        self.settings = load_settings()
        # The buffer's font and the two editor schemes are settings, so the
        # theme has to be told before the first file is drawn in it.
        self.theme.read_from(self.settings)
        self.layout = Layout.opening(self.settings)
        # Only the panels this window actually has. Offering one that does not
        # exist is worse than a shorter menu.
        self._panels: dict[str, Gtk.Widget] = {}
        # Panels put away because the window is narrow, not because anybody
        # chose to. Kept apart from the layout so widening restores the choice.
        self._folded: set[str] = set()
        self._vcs = git.Status(available=False)
        self._status_facts: dict[str, object] = {}
        self._drawer_section = "plan"
        self._statuses: dict[Path, object] = {}
        self._files = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._editor = Gtk.Stack()
        self._last_results = None
        self._known: list[workspaces.Known] = workspaces.read()
        self._engine_found: str | None = None
        self.stacks = stack_model.Definitions()
        self.stacks_rail = StacksRail(on_open=self.open_stack)
        self.clipboard_history = clipboard_history.History()
        # What this window has run. In memory for the session only.
        self.activity: list[str] = []
        # None until an index has been built. Hover, completion and the docs
        # all read it, and all of them say so rather than failing when it is
        # absent — building it is not wired yet.
        self.schema = schema_index.open_if_built()
        self._plan = None
        self._planned_at = 0.0
        self._plan_document = None
        self._plan_artifact = None
        self._applying = False
        self._apply_window = None
        # Each is false until something proves otherwise. A capability assumed
        # present is a section that promises and then shows nothing.
        # What this machine can authenticate as. Read once, from two INI files,
        # and never holding a secret — so `credentials` stops being a hardcoded
        # False that made every plan claim it could not be applied.
        self._credentials = credentials.Available()
        # What the last scan found and what the last plan would cost. Neither is
        # assumed: a workspace nobody has scanned is not a workspace with no
        # findings, and no prices is not no cost.
        self._policy = policy.Report()
        self._prices = cost.load()
        self._cost = cost.Estimate()
        self._scanning = False
        self._catalog: list = []
        # A panel being looked at without the layout having moved.
        self._peeking = ""
        self._converging = False
        self._convergence = None
        self._catalog: list = []
        # A panel being looked at without the layout having moved.
        self._peeking = ""
        self._converging = False
        self._convergence = None
        self._roles = roles.Pairing(
            reading=roles.Choice(roles.Operation.READ, None, "not read yet"),
            changing=roles.Choice(roles.Operation.CHANGE, None, "not read yet"),
        )
        # Whether Docker or Podman is here. It was hardcoded False, so the rail
        # said a rehearsal was unavailable on a machine that had a runtime
        # installed the whole time.
        self._container_runtime = runtime.detect() is not None
        self._convergence_run = False
        self._before_distraction_free: dict | None = None
        self._planning = False
        self._planning_since = 0.0
        # How far the buffer has moved since the plan in hand ran. The verdict
        # line says it out loud rather than showing the old counts as current.
        self._edits_since_the_plan = 0
        # Which setting each checkable View item reflects, so the tick can be
        # put back in step with the buffer when a setting changes elsewhere.
        self._view_toggles: dict[str, str] = {}
        # Where the caret jumped from, and where Back has been undone to.
        self._went_back: list[tuple[Path, int]] = []
        self._went_forward: list[tuple[Path, int]] = []
        # Said once per session, and never again.
        self._said_about_cursors = False
        # Which workspace the tree is pointed at, so a refresh does not rebuild
        # it and close everything somebody has opened.
        self._rail_root: Path | None = None
        self._last_errors: list = []
        self._last_warnings: list = []
        # Whether the changes have been looked at. Warnings ask to be read once,
        # and then get out of the way rather than blocking every later apply.
        self._reviewed = False
        self._setting_drawer = False
        # The one condition stopping this workspace, if there is one.
        self._blocking = None
        self._banner_is_blocking = False
        # Two panes at most, and `_files_open` is whichever has the keyboard —
        # so the eighty-nine places the window reaches into the editor follow
        # the focus without any of them knowing a split exists.
        self._editors = Split(
            lambda: Editor(
                theme=self.theme,
                on_run_file=self.run_file_tests,
                settings=self.settings,
                schema=self.schema,
                on_new_file=lambda: self.new_file(),
                on_empty=lambda: self._show_the_right_nothing(),
                on_finding=self.explain_the_finding_on,
                on_finding_menu=self.finding_menu_at,
            )
        )
        self.plan_panel = PlanPanel(on_open=self.go_to_address)
        self.test_panel = TestPanel(on_run=self.run_tests)
        self.console_panel = ConsolePanel(on_evaluate=self.evaluate)
        self.output_panel = OutputPanel()
        self.exposure_panel = ExposurePanel()
        self.cost_panel = CostPanel()
        self.drift_panel = DriftPanel(on_open=self.go_to_address, on_check=self.check_drift)
        self.git_panel = GitPanel(
            on_stage=self.stage_files,
            on_unstage=self.unstage_files,
            on_commit=self.commit_staged,
            on_push=self.ask_to_push,
            on_open=self.open_relative,
        )
        self.git_panel.show(working.Working())
        self.docs_panel = DocsPanel(
            on_search=self._search_the_schema,
            on_open=self.show_docs_for,
            on_insert=self.insert_text,
            on_caret=self.docs_for_this_resource,
        )
        # Fetched once and kept, so it works on a plane afterwards. Never
        # fetched at all unless somebody turned it on.
        self.docs = documentation.Mirror()
        self.library_panel = LibraryPanel(
            on_insert=self.insert_entry,
            on_open=self.open_entry,
            on_edit=self.edit_entry,
            on_run=self.run_command,
        )
        # Loaded when a workspace opens, because two of its four sources are
        # the workspace's own and what a workspace is about.
        self.library = library_store.Library()
        self._stops = None
        # What the last check found. Never assumed: a workspace nobody has
        # checked is not a workspace with no drift.
        self._drift = drifting.Drift()
        self._checking_drift = False
        self._drift_timer = None
        # Every provider the workspace locked, and what a registry says about
        # them. One per window, so the answers are kept for the session.
        self._providers: list[tuple[str, str, str | None]] = []
        self._versions = latest.Versions()
        # The gate sits under the changes, because it is the end of a page
        # somebody has read rather than a control on the way past.
        self.apply_gate = ApplyGate()
        self._status = {}

        self.add_css_class("tf-root")
        layout = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # One row. The menu bar, when it is on at all, is *inside* the header
        # rather than under it — a second row put minimise, maximise and close
        # below a strip of menu titles, and cost 28 pixels of every screen for
        # a row that ran 62% empty.
        self._header_widget = self._header()
        layout.append(self._header_widget)
        self._menu_bar = self._menu_titles
        layout.append(self._body())
        self._status_widget = self._status_bar()
        layout.append(self._status_widget)
        save = Gio.SimpleAction.new("save", None)
        save.connect("activate", lambda *_: self.save_current())
        self.add_action(save)

        panel = Gio.SimpleAction.new("panel", GLib.VariantType.new("s"))
        panel.connect(
            "activate",
            lambda _a, name: self.set_panel_shown(
                name.get_string(), not self.layout.is_shown(name.get_string())
            ),
        )
        self.add_action(panel)

        reset = Gio.SimpleAction.new("reset-layout", None)
        reset.connect("activate", lambda *_: self.reset_layout())
        self.add_action(reset)

        reference = Gio.SimpleAction.new("keyboard-reference", None)
        reference.connect("activate", lambda *_: self.show_keyboard_reference())
        self.add_action(reference)

        # Every annotation layer toggles on its own. These were in the
        # menu specification and wired to nothing, so choosing one did nothing.
        for name, apply in (
            ("toggle-gutter-verdicts", self._files_open.set_bands_shown),
            ("toggle-inline-explanations", self._files_open.set_bands_shown),
            ("toggle-code-lens", self._files_open.set_lens_shown),
            ("toggle-change-map", self._files_open.set_change_map_shown),
            ("toggle-hints", self._files_open.set_hints_shown),
        ):
            layer = Gio.SimpleAction.new_stateful(
                name,
                None,
                GLib.Variant.new_boolean(name not in ("toggle-code-lens", "toggle-change-map")),
            )
            layer.connect("activate", lambda action, _p, f=apply: _flip(action, f))
            self.add_action(layer)

        # Panel visibility is one parameterised action on the window and five
        # separate names in the menu. Both were right and neither could reach
        # the other — finding 007's more dangerous half.
        for name, panel in (
            ("toggle-left-rail", "left_rail"),
            ("toggle-plan-drawer", "plan_drawer"),
            ("toggle-menu-bar", "menu_bar"),
            ("toggle-status-bar", "status_bar"),
        ):
            entry = Gio.SimpleAction.new(name, None)
            entry.connect("activate", lambda *_a, p=panel: self.toggle_panel(p))
            self.add_action(entry)

        # Things the window already does, under the name the menu calls them.
        for name, run in (
            ("open-workspace", self._on_open_clicked),
            ("open-file", self._on_open_clicked),
            ("save-all", self.save_current),
            ("plan", self.plan_now),
            # The one irreversible thing in the product. It has no shortcut,
            # deliberately, and it is the last item to have had no handler.
            ("apply", self.apply_plan),
            ("reset-layout", self.reset_layout),
            ("keyboard-reference", self.show_keyboard_reference),
            ("settings", self.show_settings),
            ("close-window", self.close),
            ("full-screen", self.toggle_full_screen),
            ("close-tab", self.close_tab),
            ("goto-line", lambda: self.show_palette(":")),
            ("run-tests-in-file", self.run_tests_in_file),
            # A window with nothing in it, for a second workspace.
            ("new-window", self.open_a_new_window),
            ("revert-file", self.revert_current),
            ("cancel-run", self.cancel_the_run),
            ("goto-problem", self.go_to_the_first_problem),
            # Navigation history, which the application did not have anywhere.
            ("go-back", self.go_back),
            ("go-forward", self.go_forward),
            ("switch-file", self.switch_file),
            ("select-next-occurrence", self.select_next_occurrence),
            ("push", self.ask_to_push),
            ("switch-branch", self.switch_branch),
            # Three presets, and a preset is not a mode: touching any single
            # panel afterwards simply leaves it behind.
            ("layout-focus", lambda: self.use_layout("focus")),
            ("layout-work", lambda: self.use_layout("work")),
            ("layout-review", lambda: self.use_layout("review")),
            ("editor-font", self.show_font_settings),
            ("limits", self.show_what_it_will_not_do),
            ("release-notes", self.show_release_notes),
            ("report-a-problem", self.show_how_to_report_a_problem),
        ):
            entry = Gio.SimpleAction.new(name, None)
            entry.connect("activate", lambda *_a, f=run: f())
            self.add_action(entry)

        for name, scheme in (
            ("scheme-light", "light"),
            ("scheme-dark", "dark"),
            ("scheme-follow-system", "follow_system"),
        ):
            entry = Gio.SimpleAction.new(name, None)
            entry.connect("activate", lambda *_a, c=scheme: self.theme.prefer(c))
            self.add_action(entry)

        # Editing goes to whatever has focus, which is how every other editor
        # behaves and what the menu items promise.
        # The signal, and whatever it takes. `select-all` takes a boolean and
        # emitting it bare raises inside the handler, where nothing sees it.
        for name, signal, arguments in (
            ("undo", "text.undo", ()),
            ("redo", "text.redo", ()),
            ("cut", "cut-clipboard", ()),
            ("copy", "copy-clipboard", ()),
            ("paste", "paste-clipboard", ()),
            ("select-all", "select-all", (True,)),
        ):
            entry = Gio.SimpleAction.new(name, None)
            entry.connect("activate", lambda *_a, w=signal, g=arguments: self._to_the_editor(w, *g))
            self.add_action(entry)

        # What the editor view can be told to do about itself. **One action per
        # thing, and it both applies and persists.** There were two of each of
        # these: a stateful one that flipped the view and a plain one that wrote
        # the setting, registered under the same name — so the second replaced
        # the first, the checkmark was dead, and `toggle-whitespace` and
        # `toggle-show-whitespace` could disagree about what the buffer was
        # doing. A toggle whose tick and whose buffer disagree is worse than no
        # toggle.
        for name, key, fallback in (
            ("toggle-line-numbers", "editor.show_line_numbers", True),
            ("toggle-word-wrap", "editor.word_wrap", False),
            ("toggle-whitespace", "editor.show_whitespace", False),
            ("toggle-rulers", "editor.rulers", False),
            ("toggle-hover-popups", "editor.hover_popups", True),
        ):
            view = Gio.SimpleAction.new_stateful(
                name, None, GLib.Variant.new_boolean(bool(self.settings.get(key, fallback)))
            )
            # The setting is bound at connection time, not read out of the
            # loop variable when the action fires — every toggle would
            # otherwise write the last setting in the table.
            writes = _writes(self, key)
            view.connect("activate", lambda action, _p, apply=writes: _flip(action, apply))
            self.add_action(view)
            self._view_toggles[name] = key

        # Each part of the left rail, on its own. Folding is a click on the
        # heading; putting one away entirely is here, away from the thing it
        # removes, so it cannot happen by mis-clicking that heading.
        # Converting how a file is written. Each rewrites the buffer, so each
        # is one undo step and none of them touches a file nobody opened.
        for name, run in (
            ("zoom-in", lambda: self.zoom(1)),
            ("zoom-out", lambda: self.zoom(-1)),
            ("zoom-reset", lambda: self.zoom(0)),
            ("goto-block-start", lambda: self._go_to_block(start=True)),
            ("goto-block-end", lambda: self._go_to_block(start=False)),
            ("select-enclosing-block", self.select_enclosing_block),
            ("goto-definition", self.go_to_definition),
            ("find-references", self.find_references),
            ("convert-to-lf", lambda: self.convert_line_endings(text_handling.LineEnding.LF)),
            ("convert-to-crlf", lambda: self.convert_line_endings(text_handling.LineEnding.CRLF)),
            ("convert-to-spaces", lambda: self.convert_indentation(to_tabs=False)),
            ("convert-to-tabs", lambda: self.convert_indentation(to_tabs=True)),
            ("about", self.show_about),
            ("key-bindings", self.show_keyboard_reference),
            ("settings-workspace", self.open_workspace_settings),
            ("open-settings-folder", self.open_settings_folder),
            ("validate", self.validate_workspace),
            ("format-document", self.format_open_file),
            ("toggle-distraction-free", self.toggle_distraction_free),
            ("format-workspace", self.format_workspace),
            ("initialise", self.initialise_workspace),
            ("find", self.show_find),
            ("find-next", self._find.next),
            ("find-previous", self._find.previous),
            ("replace", self.show_find),
            ("close-others", self._files_open.close_others),
            ("close-left", self._files_open.close_before),
            ("close-right", self._files_open.close_after),
            ("close-all", self._files_open.close_all),
            ("close-saved", self._files_open.close_saved),
            ("close-gone", self._files_open.close_gone),
            ("close-untouched", self.close_untouched),
            ("pin-tab", self.pin_tab),
            ("keep-open", self.pin_tab),
            ("reveal-in-rail", self.reveal_in_rail),
            ("copy-module-source", lambda: self.copy_path("module-source")),
            ("copy-resource-addresses", self.copy_resource_addresses),
            ("open-containing-folder", self.open_containing_folder),
            ("new-file", self.new_file),
            ("new-folder", lambda: self.ask_for_a_name("New folder", self._make_folder)),
            ("rename-file", self.rename_current),
            ("duplicate-file", self.duplicate_current),
            ("delete-file", self.remove_current),
            ("save-as", self.save_as),
            ("rename-resource", self.rename_resource),
            ("exposure-analyse", self.analyse_exposure),
            ("goto-matching-bracket", self.go_to_matching_bracket),
            ("select-all-occurrences", self.select_all_occurrences),
            ("open-terminal-here", self.open_terminal_here),
            ("open-in-new-window", self.open_in_new_window),
            ("diff-against-head", self.show_diff),
            ("file-history", self.show_file_history),
            ("blame", self.show_blame),
            ("discard-changes", self.discard_changes),
            ("open-in-new-tab", self.open_in_new_tab),
            ("reopen-tab", self.reopen_tab),
            ("paste-and-indent", self.paste_and_indent),
            ("paste-from-history", self.paste_from_history),
            ("find-in-folder", self.find_in_folder),
            ("find-files-named", self.find_files_named),
            ("move-file", self.move_current),
            ("count-to-for-each", self.count_to_for_each),
            ("show-state", self.show_state),
            ("provider-docs", self.show_provider_docs),
            ("compare-with", self.compare_with),
            ("activity-log", self.show_activity_log),
            ("split-right", self.split_right),
            ("split-down", self.split_down),
            ("clone-into-split", self.clone_into_split),
            ("unsplit", self.unsplit),
            ("peek-rail", lambda: self.peek("left_rail")),
            ("peek-drawer", lambda: self.peek("plan_drawer")),
            ("keep-peeked", self.keep_peeked),
            ("apply-logs", self.show_apply_logs),
            ("stacks", self.show_stacks),
            ("git", self.show_git),
            ("clone", self.clone_a_repository),
            ("open-workspace-in-new-window", self.open_workspace_in_a_new_window),
            ("new-branch", self.new_branch),
            ("extract-to-module", self.extract_to_module),
            ("scaffold", self.show_catalog),
            ("policy-scan", self.scan_policies),
            ("policy-findings", self.show_policy_findings),
            ("show-cost", self.show_cost),
            ("explain-engine", self._say_if_the_engine_is_missing),
            ("credentials", self.show_credentials),
            ("documentation", lambda: self.show_docs()),
            ("mirrored-docs", self.show_mirrored),
            ("docs-for-resource", self.docs_for_this_resource),
            ("history", self.show_history),
            ("library", lambda: self.show_library()),
            ("library-for-resource", self.library_for_this_resource),
            ("save-to-library", self.save_selection_to_library),
            ("check-drift", self.check_drift),
            ("convergence-run", self.run_convergence),
            ("explain-finding", self.explain_finding),
            ("show-reachability", self.show_reachability),
            ("suppress-finding", self.suppress_finding),
            ("open-policy-source", self.open_policy_source),
            ("move-to-new-window", self.move_to_new_window),
        ):
            entry = Gio.SimpleAction.new(name, None)
            entry.connect("activate", lambda *_a, f=run: f())
            self.add_action(entry)

        for snippet in snippet_library.SNIPPETS:
            entry = Gio.SimpleAction.new(snippet.name, None)
            entry.connect("activate", lambda *_a, n=snippet.name: self.insert_snippet(n))
            self.add_action(entry)

        for name, by in (
            ("sort-tabs-manual", "manual"),
            ("sort-tabs-name", "name"),
            ("sort-tabs-path", "path"),
            ("sort-tabs-recent", "recent"),
            ("sort-tabs-plan-impact", "plan-impact"),
        ):
            entry = Gio.SimpleAction.new(name, None)
            entry.connect("activate", lambda *_a, b=by: self._files_open.sort_tabs(b))
            self.add_action(entry)

        for name, which in (
            ("copy-name", "name"),
            ("copy-absolute-path", "absolute"),
            ("copy-repo-path", "repository"),
            ("copy-module-path", "module"),
        ):
            entry = Gio.SimpleAction.new(name, None)
            entry.connect("activate", lambda *_a, w=which: self.copy_path(w))
            self.add_action(entry)

        # The line operations. They were dispatched by name from the menu and
        # had no action of their own, so every shortcut bound to one reached
        # nothing.
        for name in editing.OPERATIONS:
            entry = Gio.SimpleAction.new(name, None)
            entry.connect("activate", lambda *_a, n=name: self.run_line_operation(n))
            self.add_action(entry)

        for name in ("palette", "goto-file", "goto-resource"):
            entry = Gio.SimpleAction.new(name, None)
            entry.connect("activate", lambda *_a, n=name: self.show_palette(PREFIXES[n]))
            self.add_action(entry)

        preferences = Gio.SimpleAction.new("settings", None)
        preferences.connect("activate", lambda *_: self.show_settings())
        self.add_action(preferences)

        console = Gio.SimpleAction.new("toggle-console", None)
        console.connect("activate", lambda *_: self.toggle_console())
        self.add_action(console)

        tests = Gio.SimpleAction.new("run-tests", None)
        tests.connect("activate", lambda *_: self.run_tests())
        self.add_action(tests)

        # A banner for what is still true, above a toast overlay for what has
        # finished. The toast is for events, not for states.
        self._banner = Adw.Banner(button_label="Dismiss")
        self._banner_action = None
        self._banner.connect("button-clicked", lambda *_: self._banner_clicked())
        self._banner.set_revealed(False)

        banded = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        banded.append(self._banner)
        banded.append(layout)

        self._toasts = Adw.ToastOverlay()
        self._toasts.set_child(banded)
        self.set_content(self._toasts)
        # A breakpoint needs to know what the window can shrink to. Without
        # this libadwaita warns and folds nothing.
        self.set_size_request(360, 320)
        self._fold_at_every_width()

        self.register_panel("menu_bar", self._menu_bar)
        self.register_panel("left_rail", self._sidebar_widget)
        self.register_panel("status_bar", self._status_widget)
        self.register_panel("plan_drawer", self._drawer_widget)
        self._refresh_sections()

        # At capture, so a find field or a text selection cannot eat the key
        # before the window has decided what it dismisses.
        escape_closes(self, close=self._escape_dismissed_something)

        # Right-click any chrome. Works whatever is currently hidden, which is
        # the point — the thing that was lost may be the way back.
        for chrome in (self._status_widget, self._editor):
            chrome_menu.attach(chrome, self._chrome_menu)

        keys = Gtk.ShortcutController()
        keys.set_scope(Gtk.ShortcutScope.GLOBAL)
        for action, name in (("toggle-left-rail", "left_rail"),):
            accelerator = self.keymap.accelerator(action)
            if accelerator:
                keys.add_shortcut(
                    Gtk.Shortcut(
                        trigger=Gtk.ShortcutTrigger.parse_string(accelerator),
                        action=Gtk.CallbackAction.new(
                            lambda *_a, panel=name: bool(self.toggle_panel(panel)) or True
                        ),
                    )
                )
        for action, call in (
            ("keyboard-reference", self.show_keyboard_reference),
            ("reset-layout", self.reset_layout),
        ):
            accelerator = self.keymap.accelerator(action)
            if accelerator:
                keys.add_shortcut(
                    Gtk.Shortcut(
                        trigger=Gtk.ShortcutTrigger.parse_string(accelerator),
                        action=Gtk.CallbackAction.new(lambda *_a, c=call: bool(c()) or True),
                    )
                )
        self.add_controller(keys)

    def _chrome_menu(self):
        return chrome_menu.build(self.layout, self.keymap, set(self._panels))

    def _header(self) -> Gtk.Widget:
        """One row, four controls and a title. There is no second row.

        **Measured before it was changed:** at 1280 wide the header used 436px
        and the menu bar under it 487px — 66% and 62% empty — while carrying
        923px of content that fits in one row with 350 to spare. Two
        two-thirds-empty rows stacked on each other is not density, it is waste
        with a ruler on it. Chrome above the first line of code went from 92px
        to 64px, which is a line and a half of Terraform back on every screen.

        ```
        [▤] ········· prod-euw1 · eu-west-1 ▾ ········· [Plan ▾]  ⌕  ☰
        ```

        **No accent-filled button lives here in any state.** Apply is the one
        irreversible thing in the product and it belongs behind the review that
        justifies it, not one click from every screen. `Plan ▾` is quiet, and
        the caret beside it carries the whole Terraform menu — which is
        *shallower* than a menu bar for the one menu carrying capability nobody
        guesses.
        """
        header = Adw.HeaderBar()

        # A toggle for the tree, in the position a GNOME reader expects one.
        self._rail_toggle = Gtk.ToggleButton(icon_name="sidebar-show-symbolic")
        self._rail_toggle.set_tooltip_text("Show the workspace")
        self._rail_toggle.connect("toggled", self._on_rail_toggled)
        header.pack_start(self._rail_toggle)

        # The eight bar menus, flat across the header. Off by default and shown
        # by View › Menu bar; when it is on, they leave `☰` rather than
        # appearing in both places.
        self._menu_titles = menu_bar.build(self.keymap)
        self._menu_titles.set_visible(False)
        header.pack_start(self._menu_titles)

        self._switcher = WorkspaceSwitcher(
            on_open=self.switch_to,
            on_browse=self._on_open_clicked,
            on_example=(lambda: self.open_workspace(EXAMPLE_WORKSPACE))
            if EXAMPLE_WORKSPACE is not None
            else None,
            accelerator=pretty_key("<Control>o"),
        )
        header.set_title_widget(self._switcher)

        # Rightmost, because it is the least often reached for.
        self._hamburger = menu_bar.primary(self.keymap)
        header.pack_end(self._hamburger)

        search = Gtk.Button(icon_name="system-search-symbolic")
        search.add_css_class("flat")
        search.set_tooltip_text(f"Go to anything — {pretty_key('<Control>p')}")
        search.connect("clicked", lambda *_: self.show_palette())
        header.pack_end(search)

        header.pack_end(self._run_control())
        return header

    def _run_control(self) -> Gtk.Widget:
        """`Plan ▾` — the button runs the first item in its own menu.

        The Terraform menu hangs off the caret. It is the one menu carrying
        things nobody guesses at — *Check for drift*, *Analyse public access*,
        *Extract to a module* — and two clicks deep under `☰` a new user never
        finds the reason this product exists. Here it is one click from a
        control that is always visible, beside the thing they were going to
        press anyway.
        """
        split = Adw.SplitButton(label="Plan")
        split.add_css_class("tf-quiet")
        split.add_css_class("tf-run")
        split.set_tooltip_text(f"Plan this workspace — {pretty_key('<Control>Return')}")
        split.connect("clicked", lambda *_: self.plan_now())
        split.set_menu_model(context_menu.to_model(RUN_MENU, self.keymap))
        self._run_button = split
        return split

    def _on_rail_toggled(self, button: Gtk.ToggleButton) -> None:
        self.set_panel_shown("left_rail", button.get_active())

    def refresh_switcher(self) -> None:
        """Redraws the switcher from what is open and what has been opened."""
        current = self._known_workspace()
        if current is not None:
            self._known = workspaces.remember(current)
        self._switcher.show(current, self._known)
        # The branch is a fact, not an action, and it lives once — in the
        # verdict line's file facts, beside the other repository facts. It was
        # in the header as well, which is one question answered in two places.
        self.update_status(branch=self._vcs.branch or "")

    def _known_workspace(self) -> workspaces.Known | None:
        """The open workspace, as the switcher describes one."""
        if self.workspace is None:
            return None
        root = self.workspace.root_modules
        backend = next((module.backend for module in root if module.backend), "")
        drifted = len(self.stacks.problems) if self.stacks.is_declared else 0
        return workspaces.Known(
            path=self.workspace.path,
            backend=backend or "local state",
            state=f"{drifted} drifted" if drifted else "clean",
            environment=next((s.environment for s in self.stacks.stacks.values()), ""),
        )

    def switch_to(self, path: Path) -> None:
        """Opens another workspace, asking first about anything unsaved.

        Naming the consequence before acting is how the apply gate works, and
        losing an edit to a click in a popover would be worse than losing one
        to a button somebody meant to press.
        """
        unsaved = [page.path.name for page in self._files_open.pages.values() if page.modified]
        if not unsaved:
            self.open_workspace(path)
            return
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"Leave {len(unsaved)} unsaved file{'' if len(unsaved) == 1 else 's'}?",
            body=f"{', '.join(sorted(unsaved))} would be closed without saving.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save and switch")
        dialog.add_response("discard", "Switch without saving")
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def answered(_dialog, response: str) -> None:
            if response == "cancel":
                return
            if response == "save":
                for page in list(self._files_open.pages.values()):
                    if page.modified:
                        page.save()
            self.open_workspace(path)

        dialog.connect("response", answered)
        dialog.present()

    @property
    def _files_open(self) -> Editor:
        """The editor the keyboard is in."""
        return self._editors.active

    def split_right(self) -> None:
        self._split(Gtk.Orientation.HORIZONTAL)

    def split_down(self) -> None:
        self._split(Gtk.Orientation.VERTICAL)

    def _split(self, orientation: Gtk.Orientation) -> None:
        """Opens a second pane, or turns the one already open.

        The file in front comes with you: a second pane that opens empty is one
        somebody has to fill before it is worth anything.
        """
        here = self._files_open.current
        made = self._editors.split(orientation)
        if made is not None and here is not None:
            self.open_file(here.path, preview=False)

    def clone_into_split(self) -> None:
        """The same file in both panes, for reading two parts of a long one."""
        here = self._files_open.current
        if here is None:
            self._say("Open a file to put it in a split")
            return
        path = here.path
        if not self._editors.is_split:
            self._editors.split(Gtk.Orientation.HORIZONTAL)
        else:
            self._editors.focus_other()
        # For good: a split exists to hold two files at once, and a pane whose
        # tab the next open replaces is a pane with one file in it.
        self.open_file(path, preview=False)

    def unsplit(self) -> None:
        """Back to one pane, keeping whichever one you were in."""
        self._editors.unsplit()

    # Widths the panes start at. SIDEBAR and ANALYSIS are the two fixed edges;
    # the editor takes whatever is between them, which is what should grow when
    # the window does.
    SIDEBAR_WIDTH = 240
    # What collapsed leaves behind. Enough to hit with a pointer, small enough
    # that nobody would keep the rail open to avoid losing it.
    STRIP_WIDTH = 22

    # How many matches a filter opens the way to. Past this the tree is more
    # open than closed and the filter has stopped narrowing anything.
    REVEALS = 40

    # Below this the window has less room than its panes need, and GTK clips
    # rather than reflowing — so the rail is put away instead of running off
    # the edge. Measured, not chosen: the tree asks for 240 and the editor for
    # 250, plus the handle between them.
    FOLD_RAIL = 500

    def _body(self) -> Gtk.Widget:
        centre = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL, vexpand=True)
        centre.connect("notify::position", self._drawer_dragged)
        self._editor.add_named(self._empty_state(), "empty")
        # A workspace open with no file in front of you is a different state
        # from no workspace at all, and offering "Open a workspace to get
        # started" over a rail full of one is the application disagreeing with
        # itself about what is happening.
        self._editor.add_named(self._nothing_open(), "nothing-open")
        self._editor.add_named(self._editors, "file")
        self._find = FindBar(on_close=self.hide_find)
        self._find.set_visible(False)
        self._files_open.put_above_the_files(self._find)
        self._editor.set_visible_child_name("empty")
        centre.set_start_child(self._editor)

        # The four tabs. Detail is invoked rather than resident, which
        # is what keeps the rest of the window the editor.
        changes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        changes.append(self.plan_panel)
        # The rule goes with the footer. A separator over nothing is a line
        # across the bottom of the panel for no reason.
        self._footer_rule = Gtk.Separator()
        changes.append(self._footer_rule)
        changes.append(self.apply_gate)
        self.apply_gate.on_command(self.run_footer_command)
        self.apply_gate.connect(
            "notify::visible",
            lambda *_: self._footer_rule.set_visible(self.apply_gate.get_visible()),
        )

        self._drawer = Drawer(
            {
                "Changes": changes,
                EXPOSURE: self.exposure_panel,
                "Cost": self.cost_panel,
                "Tests": self.test_panel,
                "Console": self.console_panel,
                "Drift": self.drift_panel,
                "Library": self.library_panel,
                "Docs": self.docs_panel,
                "Git": self.git_panel,
                "Output": self.output_panel,
            },
            on_close=lambda: self.hide_panel("plan_drawer"),
        )
        self._drawer_widget = self._drawer

        centre.set_end_child(self._drawer)
        centre.set_resize_start_child(True)
        # The editor keeps the room. A drawer is detail you asked for, not the
        # thing you are working on — but it has to be tall enough for the one
        # message that matters most, which is why a plan failed. At 260 the
        # engine's own explanation fell below the fold.
        centre.set_shrink_end_child(False)
        # Neither may be crushed. The editor is what the window is for and the
        # drawer is what somebody opened, and a paned will happily give one of
        # them nothing.
        centre.set_shrink_start_child(False)
        self._centre = centre

        # There is no right-hand inspector. It answered the same five questions
        # the drawer answers — plan, cost, policy, public access, drift — in a
        # permanent 320-pixel column too narrow for any of them, and in every
        # view it ever drew it held four headings, two sentences of *not
        # configured* and nothing else. **One surface per question**: the
        # answers are drawer tabs, the numbers are verdict-line chips, and the
        # 320 pixels went to the buffer.
        self._sidebar_widget = self._sidebar()
        outer = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True)
        outer.set_start_child(self._sidebar_widget)
        outer.set_end_child(centre)
        outer.set_position(self._geometry.sidebar)
        outer.set_resize_start_child(False)
        outer.set_shrink_start_child(False)
        self._outer = outer
        return outer

    def _sidebar(self) -> Gtk.Widget:
        """The rail: files, and nothing else.

        Everything that was not a file has gone somewhere it belongs. The
        workspace name and its backend are in the switcher at the top of the
        window; stacks are a verdict-line chip and a full window; the plan is
        the drawer. What is left is a tree that owns the whole height, which is
        what a two-hundred-file repository needs and a heading, a count and a
        footer of grey icons were each taking a slice of.

        The filter is the one control, and it is not resident either: type into
        the rail and it appears, press Escape and it is gone.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add_css_class("tf-sidebar")

        # Hidden until somebody types. A search field sitting empty above a
        # tree is a row of height spent on a control nobody has reached for.
        self._rail_filter = Gtk.SearchEntry(placeholder_text="Filter")
        self._rail_filter.add_css_class("tf-rail-filter")
        self._rail_filter.set_visible(False)
        # `changed`, not `search-changed`: the latter is debounced by about
        # 150ms, and this is matching over a list already in memory. Waiting
        # buys nothing and makes every keystroke feel late — the palette
        # learned this and the rail was written without it.
        self._rail_filter.connect("changed", lambda *_: self._show_files())
        self._rail_filter.connect("stop-search", lambda *_: self.clear_the_rail_filter())
        box.append(self._rail_filter)

        # How much of the tree the filter is not showing. Absent when it is
        # showing all of it, which is the ordinary case.
        self._rail_hidden = Gtk.Label(xalign=0.0)
        self._rail_hidden.add_css_class("tf-micro")
        self._rail_hidden.add_css_class("tf-faint")
        self._rail_hidden.set_margin_start(10)
        self._rail_hidden.set_visible(False)
        box.append(self._rail_hidden)

        # A real tree, one level at a time. `Gtk.TreeListModel` asks for a
        # directory's children only when it is expanded, so a repository costs
        # what has been opened rather than what exists.
        self._files = FileTree(on_open=self._clicked)
        self._files.marks_from(self._marks_for)
        file_tree.install_menus(self._files, self._menu_for)
        box.append(self._files)

        # Type anywhere in the rail and the filter takes it. This is the whole
        # of what makes the rail survive a real repository, so it is not behind
        # a control somebody has to find first.
        typing = Gtk.EventControllerKey()
        typing.connect("key-pressed", self._rail_typed)
        box.add_controller(typing)

        box.set_size_request(self.SIDEBAR_WIDTH, -1)
        self._rail_scroller = box

        strip = Gtk.Button()
        strip.add_css_class("flat")
        strip.add_css_class("tf-rail-strip")
        strip.set_child(Gtk.Image.new_from_icon_name("pan-end-symbolic"))
        strip.set_tooltip_text("Show the files")
        strip.set_size_request(self.STRIP_WIDTH, -1)
        strip.set_valign(Gtk.Align.START)
        strip.connect("clicked", lambda *_: self.show_panel("left_rail"))
        strip.set_visible(False)
        self._rail_strip = strip

        holder = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        holder.append(strip)
        holder.append(box)
        return holder

    def _rail_typed(self, _controller, keyval: int, _code: int, state) -> bool:
        """A letter typed in the rail starts filtering it."""
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        if keyval == Gdk.KEY_Escape:
            return self.clear_the_rail_filter()
        said = chr(Gdk.keyval_to_unicode(keyval)) if Gdk.keyval_to_unicode(keyval) else ""
        if not said.strip() or not said.isprintable():
            return False
        self._rail_filter.set_visible(True)
        self._rail_filter.set_text(self._rail_filter.get_text() + said)
        self._rail_filter.grab_focus()
        self._rail_filter.set_position(-1)
        return True

    def clear_the_rail_filter(self) -> bool:
        """Escape puts the whole tree back, and takes the field away with it."""
        if not self._rail_filter.get_visible():
            return False
        self._rail_filter.set_text("")
        self._rail_filter.set_visible(False)
        self._show_files()
        return True

    def show_stacks(self) -> None:
        """Stacks, where somebody asking about them can find them.

        It was a permanent paragraph in the sidebar explaining a feature nobody
        had configured — teaching something to a person who is not doing it, on
        every launch, forever. The explanation is this view's empty state now,
        which is the moment somebody is actually asking.
        """
        # A window rather than a panel, and a wide one: a dependency graph in a
        # 320-pixel column is a list of names with arrows nobody can follow.
        window = Adw.Window(
            title="Stacks",
            modal=True,
            transient_for=self,
            default_width=820,
            default_height=620,
        )
        graph = StacksRail(on_open=self.open_stack)
        graph.show(self.stacks, self._radius_now(), behind=getattr(self, "_stale_stacks", set()))
        holder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        holder.append(graph)
        if not self.stacks.is_declared:
            make = Gtk.Button(label="Create stacks file")
            make.add_css_class("tf-primary")
            make.set_halign(Gtk.Align.CENTER)
            make.connect("clicked", lambda *_: self._create_stacks_file(window))
            holder.append(make)
        # A header bar and an Escape that works. Without them this was modal
        # with no way out, and opening it locked the application.
        dismissable(window, holder, title="Stacks")
        window.present()

    def _radius_now(self):
        """What the open file's stack reaches downstream, if one is open.

        The same call `refresh_stacks` makes, rather than a second way of
        working out the same thing — two answers to one question is how they
        come to disagree.
        """
        page = self._files_open.current
        if page is None or self.workspace is None:
            return None
        editing = self.stacks.containing(page.path)
        return stack_graph.consumers_of(self.stacks, editing.name) if editing else None

    def _create_stacks_file(self, window) -> None:
        """Writes the file the explanation was about, with a comment in it.

        The copy had no action attached to it, which was the other half of the
        problem: a paragraph telling somebody about a feature, with no way to
        start using it.
        """
        if self.workspace is None:
            return
        where = self.workspace.path / ".backsight" / "stacks.toml"
        if where.exists():
            self.open_file(where)
            window.close()
            return
        where.parent.mkdir(parents=True, exist_ok=True)
        where.write_text(
            "# Which modules deploy together, and what each one needs first.\n"
            "#\n"
            "# [stacks.network]\n"
            '# path = "environments/prod/network"\n'
            "#\n"
            "# [stacks.api]\n"
            '# path = "environments/prod/api"\n'
            '# needs = ["network"]\n',
            encoding="utf-8",
        )
        self._show_files()
        self.open_file(where)
        window.close()

    def show_workspace_heading(self) -> None:
        """What this workspace is, in the switcher rather than above the tree.

        It was two lines and a count at the top of the rail — a heading over the
        only section there is, saying what the title bar already says. The rail
        is the tree now, and the switcher carries the name, the backend and the
        state, which is where somebody switching workspaces is already looking.
        """
        self.refresh_switcher()

    def explain_this_backend(self) -> None:
        """The backend line is a control, not a label. It is the most common
        thing blocking somebody."""
        if self.workspace is None:
            return
        roots = self.workspace.root_modules
        if roots:
            self.explain_backend(roots[0])

    def _refresh_drift_rail(self) -> None:
        """Drift as a verdict-line chip, and only when there is drift.

        It was one row in the inspector, present whether or not it could run —
        *Drift check — Run a drift check to see what has changed outside
        Terraform*, in bold, forever, on a workspace nobody had checked. A row
        that is always there and always says nothing is a row people stop
        reading, so what is left is a chip that appears when something moved
        and a Drift tab that explains it.
        """
        self.update_status(drifted=self._drift.count or None)

    def _start_watching_for_drift(self) -> None:
        """Checks on a timer, when somebody has asked for that.

        Drift is the one thing here that is true whether or not this window is
        open, so checking it on a schedule is what makes it ambient rather than
        a command. It is off by default: a refresh costs a provider call per
        resource, and starting that against somebody's account unasked is not
        ours to decide.
        """
        if self._drift_timer is not None:
            GLib.source_remove(self._drift_timer)
            self._drift_timer = None
        minutes = int(self.settings.get("analysis.drift_every_minutes", 0) or 0)
        if minutes <= 0 or self.workspace is None:
            return

        def tick() -> bool:
            self.check_drift()
            return True

        self._drift_timer = GLib.timeout_add_seconds(minutes * 60, tick)

    # --- reusable Terraform --------------------------------------------------

    # --- git ------------------------------------------------------------------

    def refresh_git_panel(self) -> None:
        """What has changed here, as far as committing is concerned."""
        if self.workspace is None:
            return
        self.git_panel.show(working.status(self.workspace.path))

    def show_git(self) -> None:
        self.open_drawer("Git")
        self.refresh_git_panel()

    def open_relative(self, said: str) -> None:
        if self.workspace is not None:
            self.open_file(self.workspace.path / said)

    def stage_files(self, paths: list[str]) -> None:
        self._did_git(working.stage(self.workspace.path, paths) if self.workspace else "")

    def unstage_files(self, paths: list[str]) -> None:
        self._did_git(working.unstage(self.workspace.path, paths) if self.workspace else "")

    def commit_staged(self, message: str) -> None:
        """Commits what is staged. Never what merely changed."""
        if self.workspace is None:
            return
        refused = working.commit(self.workspace.path, message)
        self._did_git(refused)
        if not refused:
            self._say(f"Committed: {message}")
            self.refresh_vcs()

    def ask_to_push(self) -> None:
        """Asks first, every time.

        A push is outward-facing, somebody else can pull it a second later, and
        no amount of undo in this window reaches them. Sending it because a
        button happened to be under the pointer is not a thing this does.
        """
        if self.workspace is None:
            return
        found = working.status(self.workspace.path)
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"Push {found.branch or 'this branch'}?",
            body=(
                "This sends your commits where other people can pull them. "
                "Nothing in this window can take that back."
            ),
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("push", "Push")
        dialog.set_response_appearance("push", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", lambda _d, said: self._push() if said == "push" else None)
        dialog.present()

    def _push(self) -> None:
        self._say("Pushing…")

        def work() -> None:
            refused = working.push(self.workspace.path)
            on_main_loop(self._pushed)(refused)

        threading.Thread(target=work, name="backsight-push", daemon=True).start()

    def _pushed(self, refused: str) -> None:
        if refused:
            self._still_true(f"The push did not go: {refused}")
            return
        self._say("Pushed")
        self.refresh_git_panel()

    def _did_git(self, refused: str) -> None:
        if refused:
            self._still_true(refused)
        self.refresh_git_panel()
        self.refresh_vcs()

    def new_branch(self) -> None:
        self.ask_for_a_name("New branch", self._branch_to)

    def _branch_to(self, name: str) -> None:
        if self.workspace is None:
            return
        self._did_git(working.create_branch(self.workspace.path, name))

    # --- policy and cost ------------------------------------------------------

    def scan_policies(self) -> None:
        """Runs whichever scanner is installed, off the main loop.

        Nothing is enforced. This is a desktop application and it cannot stop
        somebody running apply in a terminal, so it says what was found and
        lets them decide — FR-POL-03.
        """
        if self._scanning or self.workspace is None or self.speculator is None:
            return
        directory = self.speculator.directory
        self._scanning = True
        self._say("Checking policies…")

        def finished(report) -> None:
            self._scanning = False
            self._policy = policy.Report(
                findings=policy.suppressed(report.findings, self._suppressed_rules()),
                passed=report.passed,
                scanner=report.scanner,
                failure=report.failure,
                ran=report.ran,
            )
            self._refresh_sections()
            self._refresh_apply()
            self._files_open.show_hints(self._hints_for_findings())
            self._say(self._policy.headline)

        def work() -> None:
            on_main_loop(finished)(
                policy.scan(directory, scanner=str(self.settings.get("policy.scanner", "checkov")))
            )

        threading.Thread(target=work, name="backsight-policy", daemon=True).start()

    def _suppressed_rules(self) -> list[str]:
        """Rules this workspace has already ruled on.

        Kept in the workspace so a suppression travels with the code and is
        reviewable in the pull request, rather than living in one person's
        editor where nobody else can see what was waved through.
        """
        if self.workspace is None:
            return []
        where = self.workspace.path / ".backsight" / "suppressed"
        try:
            return [
                line.split("#", 1)[0].strip()
                for line in where.read_text(encoding="utf-8").splitlines()
                if line.split("#", 1)[0].strip()
            ]
        except OSError:
            return []

    def _hints_for_findings(self) -> list:
        """Nothing yet — findings reach the gutter when the hint model takes
        one. Kept as its own step so the wiring is visible rather than absent."""
        return []

    def show_policy_findings(self) -> None:
        """Everything the last scan found, at the line that caused it."""
        if not self._policy.ran and not self._policy.failure:
            self.scan_policies()
            return
        if not self._policy.findings:
            self.show_output(self._policy.headline + "\n")
            return
        said = [self._policy.headline, ""]
        said.extend(
            f"  {one.where or '?':22} {one.rule:16} {one.summary}" for one in self._policy.findings
        )
        said.append("")
        said.append(
            "Nothing here is enforced. A desktop application cannot stop an apply "
            "in a terminal, so this says what was found."
        )
        self.show_output("\n".join(said))

    def _estimate_cost(self) -> None:
        """What the plan in hand does to the bill. Read from the plan alone."""
        self._prices = cost.load()
        self._cost = cost.estimate(self._plan, self._prices)

    def show_cost(self) -> None:
        """The bill, line by line, including what could not be estimated.

        It went into the output tab, which is where raw engine output goes — so
        a considered estimate arrived looking like something a subprocess
        printed, and the verdict line's cost chip had nowhere honest to point.
        """
        if self._plan is None:
            self.cost_panel.waiting("Run a plan, and what it changes about the bill will be here.")
            self.open_drawer("Cost")
            return
        self._estimate_cost()
        self.cost_panel.show(self._cost, have_prices=self._prices.any)
        self.open_drawer("Cost")

    # --- provider documentation ----------------------------------------------

    def _search_the_schema(self, term: str) -> list[tuple[str, str]]:
        """FR-SCH-08: find something by what it does when you do not know its
        name. Answers from the index, which needs no network."""
        if self.schema is None:
            return []
        try:
            return self.schema.search(term)
        except Exception:  # noqa: BLE001 - a search must never take the panel down
            return []

    def show_docs(self, term: str = "") -> None:
        """Opens the documentation, on a resource type if there is one."""
        self.open_drawer("Docs")
        if term:
            self.docs_panel.look_for(term)
            self.show_docs_for(term)
        else:
            self.docs_panel.search.grab_focus()

    def docs_for_this_resource(self) -> None:
        """The page for whatever the caret is inside."""
        self.show_docs(self._resource_under_the_caret())

    def show_docs_for(self, resource: str) -> None:
        """One page, version-matched to what the lock file says.

        Off the main loop, because the first time it is a network fetch and
        nothing about reading documentation should hold the editor still.
        """
        if not resource:
            return
        found = self._provider_of(resource)
        if found is None:
            self.docs_panel.waiting(f"Nothing in this workspace declares a provider for {resource}")
            return
        source, version = found
        self.docs.allowed = bool(self.settings.get("docs.mirror_providers", False))
        self.docs_panel.waiting(f"Looking for {resource}…")

        def finished(page) -> None:
            if page is None:
                self.docs_panel.waiting(
                    docs_panel.NOT_MIRRORED
                    if not self.docs.allowed
                    else f"No page for {resource} in {source} {version}"
                )
                return
            self.docs_panel.show(page)

        def work() -> None:
            on_main_loop(finished)(self.docs.get(resource, source=source, version=version))

        threading.Thread(target=work, name="backsight-docs", daemon=True).start()

    def _provider_of(self, resource: str) -> tuple[str, str] | None:
        """Which provider owns a resource type, and which version is locked.

        Read from the workspace rather than guessed from the prefix: two
        providers can declare a type with the same prefix, and the lock file is
        the only thing that knows which one is installed.
        """
        workspace = self.workspace
        if workspace is None:
            return None
        prefix = resource.split("_", 1)[0]
        for module in workspace.root_modules:
            for provider in module.providers:
                name = (provider.source or provider.name or "").strip()
                short = name.rsplit("/", 1)[-1]
                if short == prefix and provider.locked_version:
                    return (name if "/" in name else f"hashicorp/{short}", provider.locked_version)
        return None

    def insert_text(self, body: str) -> None:
        """Puts a block in the file, with no placeholders to fill in.

        What an example from the provider's own documentation is: correct
        already, and needing the indentation fixed rather than the values.
        """
        page = self._files_open.current
        if page is None:
            self._say("Open a file to insert into")
            return
        self._stops = Stops(page.view)
        self._stops.insert(body)
        page.view.grab_focus()

    def show_mirrored(self) -> None:
        """What documentation is on disk, by provider and version.

        FR-SCH-21. Cached data with no way to see it is data somebody discovers
        when a disk fills up.
        """
        found = self.docs.mirrored()
        if not found:
            self._say(
                "Nothing mirrored yet."
                if self.settings.get("docs.mirror_providers", False)
                else "Provider documentation is off, so nothing has been fetched."
            )
            return
        said = ["Provider documentation on this machine", ""]
        pages = 0
        for where, count in found:
            said.append(f"  {where:44} {count} page{'' if count == 1 else 's'}")
            pages += count
        said.append("")
        said.append(f"{pages} pages in {documentation.directory()}")
        self.show_output("\n".join(said))

    def read_credentials(self) -> None:
        """What this machine could authenticate as, without using any of it."""
        self._credentials = credentials.read()
        self._roles = roles.choose(
            self._credentials, preferred=str(self.settings.get("aws.profile", "") or "")
        )
        self._refresh_apply()
        self._refresh_sections()

    def show_credentials(self) -> None:
        """What was found, and which profile each operation would use."""
        found = self._credentials
        said = [found.summary]
        if found.profiles:
            said.append("")
            for profile in found.profiles:
                mark = " (default)" if profile.is_default else ""
                said.append(f"  {profile.name}{mark} — {profile.summary}")
                if profile.kind.is_long_lived:
                    said.append("      keys on disk, which anybody with the file can copy")
        said.append("")
        said.append(self._roles.summary)
        said.append(f"  {self._roles.reading.summary} — {self._roles.reading.why}")
        said.append(f"  {self._roles.changing.summary} — {self._roles.changing.why}")
        said.append("")
        said.append("Nothing here reads what is in a profile. Only that it is there.")
        self.show_output("\n".join(said))

    def record_activity(self, what, *, detail: str = "", outcome: str = "") -> None:
        """Keeps what happened, so "what did I change last Tuesday" has an answer.

        The stack goes on the record as well as the workspace, because whether
        one stack is behind another is a question about times, and this log is
        the only place the times are kept.
        """
        activity.record(
            activity.Happened(
                what=what,
                workspace=str(self.workspace.path) if self.workspace else "",
                stack=self._stack_in_hand(),
                detail=detail,
                outcome=outcome,
            )
        )

    def _stack_in_hand(self) -> str:
        """Which declared stack the module being worked on belongs to, if any."""
        page = self._files_open.current
        if page is None or not self.stacks.is_declared:
            return ""
        found = self.stacks.containing(page.path)
        return found.name if found is not None else ""

    def _refresh_stack_freshness(self) -> None:
        """The chip that replaced a resident Stacks section in the rail.

        Absent whenever nothing is stale, which is the ordinary day. A chip
        saying everything is fine is a chip nobody reads on the day it is not.
        """
        # The app owns both, so the app is what joins them: a stack reaches
        # nothing on its own, and the activity log knows nothing about stacks.
        events = [
            freshness.Event(kind=entry.what.value, stack=entry.stack, at=entry.at)
            for entry in activity.read()
            if entry.stack
        ]
        behind = freshness.stale(self.stacks, events)
        self.update_status(
            stale_stacks=len(behind),
            waiting_stacks=len(behind),
        )
        self._mark_stale_stacks({one.stack for one in behind})

    def show_apply_logs(self) -> None:
        """What every apply in this workspace actually printed."""
        if self.speculator is None:
            self._say("Open a file to see this workspace's applies")
            return
        found = applying.kept_for(self.speculator.directory)
        if not found:
            self._say("No applies have been run here yet")
            return
        self.show_output(found[-1].read_text(encoding="utf-8"))
        self._say(f"{len(found)} kept — showing the newest")

    def show_history(self) -> None:
        """Every plan, apply and drift check on record, oldest first.

        Not the activity log, which is this session's subprocess invocations —
        FR-APP-29 against FR-SEC-08. One answers "what did that command
        actually run"; this answers "what did I change last Tuesday".
        """
        found = activity.read()
        if not found:
            self._say("Nothing has been recorded yet")
            return
        self.show_output(activity.as_text(found))

    def load_library(self) -> None:
        """Reads every source. Generated entries wait until they are asked for.

        A provider index holds thousands of resource types, and building two
        entries for every one of them to show a list of ten is work nobody
        asked for — so the schema half answers a search rather than a load.
        """
        shared = str(self.settings.get("library.shared_path", "") or "").strip()
        self.library = library_store.load(
            workspace=self.workspace.path if self.workspace else None,
            shared=Path(shared).expanduser() if shared else None,
            generated=self._catalog_entries(),
        )
        self.library_panel.show(self.library)
        self.library_panel.ask_the_schema(self._generated_entries)
        for broken in self.library.broken:
            self._say(f"{Path(broken.path).name} is not an entry: {broken.why}")

    def _generated_entries(self, term: str) -> list:
        """Entries for the resource types whose name matches what was typed."""
        if self.schema is None:
            return []
        house = conventions.from_settings(self.settings)
        try:
            found = generated.matching(self.schema, term.strip().lower(), limit=8)
            if not house.any:
                return found
            where = self._environment()
            return [
                replace(one, body=conventions.apply(one.body, house, environment=where))
                for one in found
            ]
        except Exception:  # noqa: BLE001 - a search must never take the panel down
            return []

    def _catalog_entries(self) -> list:
        """The module catalog, as library entries.

        Where an approved module exists for the thing somebody is writing, it
        belongs in front of them at the same moment as the raw resource type —
        not in a separate place they have to remember to look.
        """
        where = str(self.settings.get("catalog.path", "") or "").strip()
        if not where:
            return []
        found = catalog_modules.catalog(Path(where).expanduser())
        self._catalog = found
        return catalog_modules.as_entries(
            found, source=str(self.settings.get("catalog.source", "") or "").strip()
        )

    def show_catalog(self) -> None:
        """Every module in the catalog, and what each one needs."""
        if not self._catalog:
            self._say("No module catalog configured. Point at a folder in Preferences.")
            return
        said = [f"{len(self._catalog)} module{'' if len(self._catalog) == 1 else 's'}", ""]
        for module in self._catalog:
            said.append(f"  {module.name} — {module.summary}")
            if module.about:
                said.append(f"      {module.about}")
            for one in module.required:
                said.append(f"      {one.name}: {one.description or one.type}")
            said.append("")
        self.show_output("\n".join(said))

    def show_library(self, term: str = "") -> None:
        """Opens the library, searching for something if there is something."""
        self.open_drawer("Library")
        if term:
            self.library_panel.look_for(term)
        self.library_panel.search.grab_focus()

    def library_for_this_resource(self) -> None:
        """Everything the library has about the resource under the caret."""
        found = self._here()
        if found is None:
            self.show_library()
            return
        _page, source, line = found
        block = navigation.enclosing(source, line)
        self.show_library(getattr(block, "type", "") or "")

    def insert_entry(self, entry) -> None:
        """Puts an entry in the file, and selects the first thing to fill in."""
        page = self._files_open.current
        if page is None:
            self._say("Open a file to insert into")
            return
        self._stops = Stops(page.view)
        filled = self._stops.insert(entry.body)
        page.view.grab_focus()
        if filled.has_stops:
            self._say(f"{entry.name} — Tab moves to the next field")
        else:
            self._say(f"{entry.name} inserted")

    def open_entry(self, entry) -> None:
        """An example becomes a file; a runbook is read where it is."""
        if entry.is_a_runbook:
            self.open_drawer("Library")
            return
        if self.workspace is None:
            self._say("Open a workspace first")
            return
        where = self.workspace.path / library_entry.file_name(entry.name)
        if where.exists():
            self._still_true(f"{where.name} is already there. Nothing was written.")
            return
        where.write_text(placeholders.resolve(entry.body).text, encoding="utf-8")
        self._show_files()
        self.open_file(where)

    def edit_entry(self, entry) -> None:
        """Opens the file the entry is written in, because it is a file."""
        if entry.path is None:
            self._say("That one is generated, so there is no file to edit")
            return
        self.open_file(Path(entry.path))

    def save_selection_to_library(self) -> None:
        """The block you already wrote, kept so you never write it again.

        This is the answer to the complaint. The most useful entry anybody has
        is the one they are looking at, and it costs a name.
        """
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        bounds = page.buffer.get_selection_bounds()
        if not bounds:
            self._say("Select the block you want to keep")
            return
        body = page.buffer.get_text(bounds[0], bounds[1], True)
        self._ask_for_a_name(body)

    def _ask_for_a_name(self, body: str) -> None:
        """One question, because an entry without a name cannot be found again."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Save to library",
            body="What should this be called?",
        )
        field = Gtk.Entry(placeholder_text="Private bucket with access logs")
        field.set_margin_start(12)
        field.set_margin_end(12)
        dialog.set_extra_child(field)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")

        def answered(_dialog, response: str) -> None:
            if response != "save":
                return
            name = field.get_text().strip()
            if not name:
                self._say("An entry needs a name to be found again")
                return
            self._keep(name, body)

        field.connect("activate", lambda *_: dialog.emit("response", "save"))
        dialog.connect("response", answered)
        dialog.present()

    def _keep(self, name: str, body: str) -> None:
        entry = library_entry.Entry(
            name=name,
            kind=library_entry.Kind.SNIPPET,
            body=body.strip("\n") + "\n",
            source=library_entry.Source.YOURS,
            resource=self._resource_under_the_caret(),
        )
        try:
            where = library_store.save(entry)
        except OSError as refused:
            self._still_true(f"That could not be saved: {refused}")
            return
        self.load_library()
        self.read_credentials()
        self.show_workspace_heading()
        self.show_what_is_blocking()
        self._say(f"Saved {name} to your library")
        self.activity.append(f"library: saved {name} to {where}")

    def _resource_under_the_caret(self) -> str:
        """The resource type this came from, so it can be found from one later."""
        found = self._here()
        if found is None:
            return ""
        _page, source, line = found
        block = navigation.enclosing(source, line)
        return getattr(block, "type", "") or ""

    def run_command(self, command: str) -> None:
        """A runbook step's command, handed over rather than run.

        A step says `tofu apply -target=…`. Running that from a click is an
        apply nobody confirmed, so the command goes to the console where it can
        be read, and to the clipboard where it can be pasted.
        """
        self.get_clipboard().set(command)
        self.show_output(f"Copied, not run:\n{command}\n")
        self._say("Copied to the clipboard — a runbook step is not run from here")

    def check_drift(self) -> None:
        """Asks the engine what has moved. Read-only, by construction."""
        if self._checking_drift or self.workspace is None or self.speculator is None:
            return
        directory = self.speculator.directory
        self._checking_drift = True
        self._refresh_drift_rail()

        def finished(found) -> None:
            self._checking_drift = False
            self._drift = found
            self.drift_panel.show(found)
            self._refresh_drift_rail()
            self.record_activity(
                activity.What.DRIFT, outcome=found.headline if found.checked else "could not run"
            )
            self.update_status(drifted=found.count)

        def work() -> None:
            on_main_loop(finished)(drifting.check(directory))

        threading.Thread(target=work, name="backsight-drift", daemon=True).start()

    def show_drift(self) -> None:
        """Opens the detail. What `3 drifted` in the status bar now does."""
        self.open_drawer("Drift")

    def go_to_address(self, address: str) -> None:
        """Opens wherever a resource address is declared."""
        found = self._references_to(address)
        if not found:
            self._say(f"{address} is not declared in this workspace")
            return
        path, line = found[0]
        self.open_at(path, line)

    def _empty_state(self) -> Gtk.Widget:
        """What the window says before a workspace is open.

        **Three ways in and a list of what you had.** No illustration, no
        product tour, and no empty rail pretending a workspace is loaded.

        The example workspace is the fourth and it is deliberately quieter: it
        plans offline against the engine's own resource, with no provider, no
        credentials and no network, so it is the fastest path from install to
        seeing the thing work — and it works on a plane. It is a demo, and the
        other three are what somebody actually does.
        """
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)

        title = Gtk.Label(label="Open a workspace to get started")
        title.add_css_class("tf-title")
        box.append(title)

        detail = Gtk.Label(
            label=(
                "Point Backsight at a folder with .tf files and it will read "
                "your state and providers."
            ),
            wrap=True,
            justify=Gtk.Justification.CENTER,
        )
        detail.add_css_class("tf-faint")
        detail.add_css_class("tf-small")
        box.append(detail)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_halign(Gtk.Align.CENTER)
        buttons.set_margin_top(8)
        for label, action, primary in (
            ("Open workspace…", "win.open-workspace", True),
            ("Open a file…", "win.open-file", False),
            ("Clone a repository…", "win.clone", False),
        ):
            button = Gtk.Button(label=label)
            button.add_css_class("tf-primary" if primary else "tf-quiet")
            button.connect("clicked", lambda *_a, name=action: self.activate_action(name, None))
            buttons.append(button)
        box.append(buttons)

        # What you had. A list of names rather than a row of buttons: this is
        # the one part of the screen that is about your own history.
        recent = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        recent.set_halign(Gtk.Align.CENTER)
        recent.set_margin_top(10)
        for known in self._known[:5]:
            row = Gtk.Button(label=known.path.name)
            row.add_css_class("flat")
            row.add_css_class("tf-clickable-host")
            row.add_css_class("tf-small")
            row.set_tooltip_text(str(known.path))
            row.connect("clicked", lambda *_a, where=known.path: self.open_workspace(where))
            recent.append(row)
        recent.set_visible(bool(self._known))
        box.append(recent)

        # A button rather than a `Gtk.LinkButton`: that draws in the desktop's
        # own link colour, which on a red-accented desktop puts the friendliest
        # thing on this screen in the colour that means destroy everywhere else.
        example = EXAMPLE_WORKSPACE
        if example is not None:
            shown = Gtk.Button(label="or try an example workspace")
            shown.add_css_class("flat")
            shown.add_css_class("tf-clickable-host")
            shown.add_css_class("tf-small")
            shown.add_css_class("tf-accent")
            shown.set_tooltip_text(
                "Plans offline against the engine's own resource — no provider, "
                "no credentials, no network."
            )
            shown.connect("clicked", lambda *_a, path=example: self._open_example(path))
            shown.set_halign(Gtk.Align.CENTER)
            shown.set_margin_top(6)
            box.append(shown)
        return box

    def _show_the_right_nothing(self) -> None:
        """Which nothing to show: no workspace, or a workspace with nothing open.

        They are different states and they want different sentences. Showing
        the first over a rail full of modules is the application disagreeing
        with itself about what is happening.
        """
        if self._files_open.pages:
            return
        self._editor.set_visible_child_name(
            "nothing-open" if self.workspace is not None else "empty"
        )

    def _nothing_open(self) -> Gtk.Widget:
        """A workspace is open and no file is. Say that, and say what to do.

        What is true, why you are seeing it, and what to do next — in that
        order, and it stops at the third because there is a real next action.
        """
        return empty_state.build(
            "Nothing open",
            "Pick a file from the rail, or search for one.",
            glyph="▤",
            action=f"Go to anything — {pretty_key('<Control>p')}",
            on_act=self.show_palette,
        )

    def _open_example(self, path: Path) -> bool:
        """Opens the demo. Returns True, which is what a link handler owes."""
        self.open_workspace(path)
        return True

    def show_output(self, text: str) -> None:
        """Puts what the engine printed where somebody can read it.

        It used to reveal an empty `Gtk.Box` and discard the text — twelve
        callers handed it output and none of it was ever drawn. What the pane
        did do was hold the bottom of the window open once anything had run, so
        closing the drawer left a grey band nothing could use.
        """
        if not text.strip():
            return
        self.output_panel.show(text)
        self.open_drawer("Output")

    def _refresh_plan_rail(self) -> None:
        """Nothing: the plan lives in the drawer, and its counts in the verdict line.

        Kept as a name because a dozen call sites refresh "the plan rail" after
        something changes, and each of them still means *the plan is different
        now* — which the drawer and the verdict line both read for themselves.
        """

    def _describe_sections(self) -> list[analysis_sections.Section]:
        """Every section, from the one plan the rest of the rail is showing."""
        return analysis_sections.describe(self._plan, self._capabilities())

    def _capabilities(self) -> analysis_sections.Capabilities:
        """What this installation can actually do. Nothing here is assumed.

        Every one of these is false until something proves otherwise, because a
        section claiming to be ready and then showing nothing is the failure
        this whole derivation exists to remove.
        """
        return analysis_sections.Capabilities(
            policy_set=self._policy.ran,
            credentials=self._credentials.any,
            container_runtime=self._container_runtime,
            pricing_data=self._prices.any,
            policy_said=self._policy.headline if self._policy.ran or self._policy.failure else "",
            cost_said=self._cost.headline if self._plan is not None else "",
            convergence_run=self._convergence_run,
        )

    def _refresh_apply(self) -> None:
        """Sets the gate from the plan and from whatever is stopping it.

        The blocker and the hint read one source, so they cannot disagree about
        why applying is not possible.
        """
        now = self._situation()
        self.apply_gate.show(now)
        self.mark_the_run_control(now)

    def mark_the_run_control(self, now: footer_model.Situation) -> None:
        """The primary carries the plan's own worst consequence, and only then.

        A control that looks the same whether the plan creates two things or
        destroys forty is withholding the one fact somebody needs before they
        press it.
        """
        control = getattr(self, "_run_button", None)
        if control is None:
            return
        control.set_visible(self.a_plan_could_run())
        destructive = bool(now.irreversible)
        control.remove_css_class("tf-irreversible")
        if destructive:
            control.add_css_class("tf-irreversible")
            control.remove_css_class("tf-quiet")
        else:
            control.add_css_class("tf-quiet")

    def a_plan_could_run(self) -> bool:
        """Whether pressing it could do anything at all.

        *Will not run* is the workspace, not the last attempt: with no engine
        or nothing open there is nothing to press, so the control goes. A plan
        that failed keeps it, because trying again is exactly what you want.
        """
        return self.workspace is not None and bool(self._engine_version())

    def _situation(self) -> footer_model.Situation:
        """Everything the footer's decision reads, from one place.

        The footer, the status bar and the drawer all describe the same plan.
        Building the description once is what stops them disagreeing.
        """
        changes = len(getattr(self._plan, "changes", ())) if self._plan is not None else 0
        blocked = analysis_sections.why_apply_is_blocked(self._plan, self._capabilities(), changes)
        return footer_model.Situation(
            plan=self._plan,
            running=self._planning,
            elapsed=self._planning_for(),
            errors=self._last_errors,
            warnings=self._last_warnings,
            changes=changes,
            irreversible=_irreversible_count(self._plan),
            environment=self._environment(),
            fixable=self._anything_fixable(),
            reviewed=self._reviewed,
            blocked=blocked or "" if self._plan is not None else "",
            plan_age=self._plan_age(),
            local_state=not self._has_a_backend(),
        )

    def _plan_age(self) -> float:
        """How long ago the plan in hand was taken, in seconds."""
        if self._plan is None or not self._planned_at:
            return 0.0
        return max(0.0, time.monotonic() - self._planned_at)

    def _anything_fixable(self) -> bool:
        """Whether any error has an edit that follows from the text."""
        source = self._source_of(self._last_errors)
        return any(
            repair.explain(error, source.get(error.path, "")).is_fixable
            for error in self._last_errors
        )

    def _planning_for(self) -> float:
        return max(0.0, time.monotonic() - self._planning_since) if self._planning else 0.0

    def _environment(self) -> str:
        """What has to be typed out, from the stack this workspace declares."""
        for stack in self.stacks.stacks.values():
            if stack.environment:
                return stack.environment
        return self.workspace.path.name if self.workspace is not None else ""

    def _refresh_sections(self) -> None:
        """Rewrites every section's line from the current plan.

        The drawer's Exposure tab reads the same sentence, because two places
        wording the same fact differently is the contradiction the design exists
        to stop — and it came back the moment there were two places.
        """
        self._refresh_plan_rail()
        self._refresh_drift_rail()
        for described in self._describe_sections():
            if described.title == EXPOSURE and described.is_empty:
                self.exposure_panel.waiting(described.detail)
        self._badge_the_drawer()

    def _badge_the_drawer(self) -> None:
        """How much each tab has to say, on the tab.

        **Quiet when there is nothing.** A badge reading nought is a badge
        people stop reading, and it takes the badge that means something down
        with it.
        """
        if not hasattr(self, "_drawer"):
            return
        self._drawer.count("Changes", len(self._plan.changes) if self._plan else 0)
        self._drawer.count(EXPOSURE, self.exposure_panel.count)
        self._drawer.count("Drift", self._drift.count)
        self._drawer.count("Tests", self._last_results.failed if self._last_results else 0)

    def _status_bar(self) -> Gtk.Widget:
        """The verdict line: twenty-four pixels, three zones, and it never leaves.

        It is the product's answer to its own question, and the one element
        allowed to change its own background — which it does for exactly one
        condition, a plan that will not run.
        """
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        bar.add_css_class("tf-verdict")
        # The verdict never drops. The chips do, so they are the only zone that
        # is allowed to give room back.
        self._status_verdict = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._status_chips = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._status_position = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        bar.append(self._status_verdict)
        bar.append(self._status_chips)
        bar.append(Gtk.Box(hexpand=True))
        bar.append(self._status_position)
        self._status_widget = bar
        # What the last build produced, so narrowing can re-fit without asking
        # the engine to rebuild the same line.
        self._status_line = status_line.VerdictLine()
        # How many chips are on screen, so a resize that changes nothing does
        # not rebuild the row — and -1, so the first draw always does.
        self._chips_shown = -1
        self._chip_widths: dict[str, int] = {}
        bar.connect("notify::width", lambda *_: self._fit_the_chips())
        self.update_status()
        return bar

    def update_status(self, **facts: object) -> None:
        """Rebuilds the line from what is actually known.

        Anything unknown is left out rather than shown as a zero. Five negatives
        in a row become facts, and only the thing blocking the next action is
        coloured.
        """
        # `None` means forget this fact, not leave it alone. A measurement that
        # is no longer true has to be able to leave the line, or the strip shows
        # the last run's numbers beside this run's error.
        for key, value in facts.items():
            if value is None:
                self._status_facts.pop(key, None)
            else:
                self._status_facts[key] = value
        self._status_line = status_line.build(**self._status_facts)
        self._chips_shown = -1
        self._draw_status(self._status_line)

    def _draw_status(self, line) -> None:
        for box, segments in (
            (self._status_verdict, line.verdict),
            (self._status_chips, line.chips),
            (self._status_position, line.facts),
        ):
            while (child := box.get_first_child()) is not None:
                box.remove(child)
            for segment in segments:
                box.append(self._status_segment(segment))
        # The strip turns, once, for the one thing worth taking a whole strip
        # of the window for.
        if line.will_not_run:
            self._status_widget.add_css_class("tf-will-not-run")
        else:
            self._status_widget.remove_css_class("tf-will-not-run")
        self._fit_the_chips()

    def _fit_the_chips(self) -> None:
        """Drops chips off the right, cheapest first, until the line fits.

        Measured rather than guessed at a breakpoint: the same width holds four
        chips in one workspace and two in another, because the verdict and the
        file facts are not the same length in both.
        """
        room = self._status_widget.get_width()
        if room <= 0:
            return
        wanted = self._status_line.chips
        fixed = sum(
            box.get_preferred_size()[1].width
            for box in (self._status_verdict, self._status_position)
        )
        # The margins the strip carries, plus the gap that keeps the chips from
        # touching the file facts. What is left is what the chips may have.
        spare = room - fixed - CHIP_MARGIN
        order = sorted(range(len(wanted)), key=lambda at: -wanted[at].weight)
        fits = len(wanted)
        while fits:
            shown = sorted(order[:fits])
            width = sum(self._chip_width(wanted[at]) for at in shown)
            if width <= spare:
                break
            fits -= 1
        if fits == self._chips_shown:
            return
        self._chips_shown = fits
        box = self._status_chips
        while (child := box.get_first_child()) is not None:
            box.remove(child)
        for segment in self._status_line.within(fits).chips:
            box.append(self._status_segment(segment))

    def _chip_width(self, segment) -> int:
        """What one chip asks for, measured once and remembered.

        Measuring means building a label, and building a label inside a
        size-allocate is how a resize turns into a loop.
        """
        found = self._chip_widths.get(segment.text)
        if found is None:
            label = Gtk.Label(label=segment.text)
            label.add_css_class("tf-micro")
            found = label.get_preferred_size()[1].width + CHIP_GAP
            self._chip_widths[segment.text] = found
        return found

    def _status_segment(self, segment) -> Gtk.Widget:
        # Cut at the end, where a reader expects it. A diagnostic summary is
        # long enough to be trimmed and it was being trimmed at the front, so
        # the line read "rovisioner (main.tf:62) · and 4 more" and the word it
        # cut into was the one naming the problem.
        label = Gtk.Label(label=segment.text, ellipsize=Pango.EllipsizeMode.END)
        label.set_max_width_chars(48)
        label.add_css_class("tf-micro")
        label.add_css_class(TONE_CLASSES.get(segment.tone, "tf-faint"))
        if not segment.is_clickable:
            return label
        # Dotted underlines mark clickable segments; clicking opens the drawer
        # at the section the number is about.
        label.add_css_class("tf-clickable")
        button = Gtk.Button(child=label)
        button.add_css_class("flat")
        button.add_css_class("tf-clickable-host")
        button.set_tooltip_text(segment.tooltip or f"Open {segment.action}")
        button.connect("clicked", lambda *_a, name=segment.action: self.open_drawer(name))
        return button

    # A verdict-line chip whose answer is not a drawer tab. Each is a real
    # surface somewhere else, and a chip that opens the drawer and then says
    # "there is no such tab" is a chip that lied about being clickable.
    # A verdict-line chip whose answer is not a drawer tab of the same name.
    # Each of these is a real surface somewhere, and a chip that opens the
    # drawer and then says "there is no such tab" is a chip that lied about
    # being clickable.
    ELSEWHERE = {
        # A graph needs a window, not a drawer too narrow to draw one in.
        "stacks": "show_stacks",
        "format": "format_open_file",
        "backend": "explain_this_backend",
    }

    # And the ones that are a tab under a different name. The chip is named for
    # the question; the tab is named for the answer.
    AS_A_TAB = {
        "plan": "Changes",
        # Not a tab of its own: the plan panel already renders every diagnostic
        # with the line it is on and the fix for it, and a second surface for
        # the same thing is the duplication this design deletes everywhere else.
        "problems": "Changes",
        "exposure": EXPOSURE,
        # The rehearsal writes what the emulator said, and that is what a
        # coverage figure is about.
        "convergence": "Output",
        "credentials": "Output",
    }

    def open_drawer(self, section: str) -> None:
        """Clicking a verdict-line chip opens whatever answers it."""
        wanted = section.strip().lower()
        if wanted in self.ELSEWHERE:
            getattr(self, self.ELSEWHERE[wanted])()
            return
        section = self.AS_A_TAB.get(wanted, section)
        self.show_panel("plan_drawer")
        if section.strip().lower() == "git":
            # Its buttons are about the repository, so ask about it now rather
            # than showing whatever the last workspace left behind.
            self.refresh_git_panel()
        if not self._drawer.show_section(section):
            # A section nobody built is not an error; the drawer opens where it
            # was rather than pretending to have gone somewhere.
            self._say(f"There is no {section} tab yet")

    def _settle_the_rail(self) -> None:
        """Shown is the rail, collapsed is the strip, hidden is nothing.

        Collapsed used to draw exactly what shown drew, so the everyday toggle
        flipped between two identical states and the rail read as permanent.
        """
        if not hasattr(self, "_rail_strip"):
            return
        where = self.layout.visibility("left_rail")
        collapsed = where is Visibility.COLLAPSED
        self._rail_strip.set_visible(collapsed)
        self._rail_scroller.set_visible(where is Visibility.SHOWN)
        if where is Visibility.SHOWN:
            self._outer.set_position(self._geometry.sidebar)
        elif collapsed:
            self._outer.set_position(self.STRIP_WIDTH)

    def _settle_the_bottom(self) -> None:
        """Closed means the space comes back, not that the panel went invisible.

        A paned holds its position when a child is hidden, so closing the drawer
        left a grey band between the editor and the status bar that nothing
        could use.
        """
        showing = self._drawer.get_visible()
        if showing:
            self._size_drawer()
            return
        self._setting_drawer = True
        self._centre.set_position(self._centre.get_height())
        self._setting_drawer = False

    def _size_drawer(self) -> None:
        """As tall as its content needs, or as tall as it was last dragged to.

        Capped either way. One diagnostic filling nearly half the window is the
        panel deciding the failure matters more than the file it happened in,
        and past the cap it scrolls instead of growing.
        """
        window = self._centre.get_height() or self.get_height()
        if window <= 0:
            # Nothing has been laid out yet, so there is no height to divide.
            # Dividing zero puts the drawer at zero and leaves it there — the
            # same way the inspector took the editor to nothing.
            return
        chosen = panels.read(str(self.workspace.path)) if self.workspace else None
        # Never dragged here: open at the same fraction every time rather than
        # at whatever this tab's content happens to want.
        wanted = chosen if chosen else panels.first_height(window)
        height = panels.height_for(wanted, window, dragged=chosen is not None)
        self._setting_drawer = True
        self._centre.set_position(max(0, window - height))
        self._setting_drawer = False

    def _drawer_dragged(self, *_args) -> None:
        """Records a height somebody chose, and never one this computed."""
        if self._setting_drawer or self.workspace is None:
            return
        if not self.layout.is_shown("plan_drawer"):
            return
        window = self._centre.get_height()
        height = window - self._centre.get_position()
        if window > 0 and height > 0:
            panels.remember(str(self.workspace.path), height)

    def _escape_dismissed_something(self) -> bool:
        """What Escape closes, outermost first, one press each.

        Returning `False` lets the press through — which is what an editor with
        nothing open should do with it, rather than swallowing every Escape in
        the application for no reason.
        """
        # **Innermost first.** A snippet's fields are inside the buffer, so
        # leaving them has to happen before anything around the buffer closes —
        # otherwise one press takes the drawer and leaves you still in a field.
        # The window's own controller runs before the view's, so the view is
        # asked here rather than left to catch what is left.
        stops = getattr(self, "_stops", None)
        if stops is not None and stops.is_live:
            stops.stop()
            return True
        if self.stop_peeking():
            return True
        if self._rail_filter.get_visible():
            return self.clear_the_rail_filter()
        if self._find.get_visible():
            self.hide_find()
            return True
        if self.layout.is_shown("plan_drawer"):
            self.hide_panel("plan_drawer")
            return True
        if self._banner.get_revealed():
            self.dismiss_banner()
            return True
        return False

    # --- opening a workspace ------------------------------------------------

    def _on_open_clicked(self, _button: Gtk.Button | None = None) -> None:
        dialog = Gtk.FileDialog(title="Open a workspace")
        dialog.select_folder(self, None, self._on_folder_chosen)

    def _on_folder_chosen(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            # Cancelling is not a failure and has nothing to report.
            return
        if folder is not None and folder.get_path():
            self.open_workspace(Path(folder.get_path()))

    def save_current(self) -> None:
        """Writes the open file, then asks for a plan about it."""
        page = self._files_open.current
        if page is None:
            return
        page.save(
            trim=bool(self.settings.get("editor.trim_trailing_whitespace_on_save", True)),
            final_newline=bool(self.settings.get("editor.ensure_final_newline", True)),
        )
        # The setting existed in Preferences and nothing read it, so turning it
        # on did nothing at all.
        if self.settings.get("terraform.format_on_save", False):
            self.format_open_file()
        self.refresh_vcs()
        if self.speculator is not None and self.settings.get("terraform.plan_on_save", True):
            self.speculator.touched()
        if self.settings.get("analysis.convergence_on_save", False):
            self.run_convergence(asked=False)

    def refresh_vcs(self) -> None:
        """Recomputes git rather than clearing it.

        A refresh that fails keeps the previous answer and marks it stale. Going
        blank would make every tab read as unchanged, which is a claim.
        """
        if self.workspace is None:
            return
        self._vcs = git.read(self.workspace.path, previous=self._vcs)
        self._refresh_statuses()

    def _refresh_statuses(self, plan=None) -> None:
        # Every file in the rail, not only the open ones: a rail row that goes
        # unmarked because nobody happened to open it reads as unchanged.
        paths = list(dict.fromkeys([*self._files_open.pages, *self._files.rows]))
        source_map = None
        if plan is not None and self.workspace is not None and self.speculator is not None:
            module = self.workspace.module_at(self.speculator.directory)
            if module is not None:
                source_map = SourceMap.build(self.workspace, module)
        self._statuses = for_files(
            paths,
            plan=plan,
            source_map=source_map,
            vcs=self._vcs if self._vcs.available else None,
            unsaved={p for p, page in self._files_open.pages.items() if page.modified},
            unreadable=set(),
        )
        self._files_open.show_statuses(self._statuses)
        self._mark_rail_rows()

    def _mark_stale_stacks(self, names: set[str]) -> None:
        """Which stacks are behind something they depend on.

        The chip in the verdict line says *something* is stale; the Stacks view
        says which. The rail is a file tree and stays one — a stack is not a
        folder, and hanging a stack's state off a directory row was asking a
        tree to carry a fact it has no row for.
        """
        self._stale_stacks = names

    def _mark_rail_rows(self) -> None:
        """Re-asks the tree what to put on each row that is on screen.

        **Nothing is rebuilt.** A tree rebuilt every time a plan finishes is a
        tree that closes under you, and what somebody has opened is the only
        state in the rail worth anything.
        """
        self._files.remark()

    def _mark_the_current_file(self, path: Path) -> None:
        """The file in front, marked in the tree."""
        self._files.mark_current(path)

    def _reveal_in_rail(self, path: Path) -> None:
        """Opens the ancestors of the file in front, and nothing else.

        **Always, not on a setting.** A file opened from the palette, from a
        finding or from a plan row is one you asked for by name, and leaving it
        somewhere in a collapsed tree is leaving you to go and find it again —
        which is what the setting was really protecting against when the rail
        was a flat list that scrolled under you. Only its own ancestors open.
        """
        self._files.reveal(Path(path).resolve())

    def _plan_went_stale(self) -> None:
        """The first edit after a plan clears its markers, rather than dimming.

        A dimmed marker still reads as information, and a stale plan marker is a
        confident lie.
        """
        if self._status_facts.get("counts"):
            # The counts stay, because they are still the best answer anybody
            # has — but they are marked as of when, which is the difference
            # between a stale answer and a confident lie.
            self._edits_since_the_plan += 1
            self.update_status(stale_edits=self._edits_since_the_plan)
        if not self._statuses:
            return
        if not self.settings.get("tabs.indicators.clear_plan_on_edit", True):
            return
        self._statuses = cleared_of_plan(self._statuses)
        self._files_open.show_statuses(self._statuses)

    def _module_for(self, path: Path) -> Path | None:
        """The module a file belongs to.

        The plan follows the file being edited. A workspace with several root
        modules has no single answer to "what would a plan do", and picking the
        first one would answer a question nobody asked.
        """
        if self.workspace is None:
            return None
        found = self.workspace.module_at(path.parent)
        return found.path if found else None

    def _watch(self, module: Path) -> None:
        """Points the speculator at one module, replacing whatever it watched."""
        if self.speculator is not None:
            if self.speculator.directory == module:
                return
            self.speculator.cancel()
        self.speculator = Speculator(
            module,
            debounce=max(0.0, int(self.settings.get("terraform.plan_debounce_ms", 800)) / 1000),
            on_progress=on_main_loop(self._on_progress),
            on_plan=on_main_loop(self._on_plan),
        )
        self.plan_panel.waiting(self._how_a_plan_starts(module))

    def _how_a_plan_starts(self, module: Path) -> str:
        """What actually starts a plan here, which is a setting rather than a fact.

        It said "Save to plan" whatever the setting said, so with planning on
        save turned off the rail was telling somebody to do a thing that would
        not work.
        """
        if self.settings.get("terraform.plan_on_save", True):
            return f"Save to see what would change in {module.name}"
        return f"Run a plan to see what would change in {module.name}"

    def _plan_failed(self, outcome: PlanOutcome) -> None:
        """Says what the engine said, and keeps the whole of it reachable.

        Everything downstream is cleared first. A failed plan leaving the last
        plan's verdicts, counts and blocker on screen is the panel disagreeing
        with itself, which is the thing this application must never do.
        """
        self._planning = False
        self._plan = None
        self._planned_at = 0.0
        self._plan_document = None
        self._plan_artifact = None
        self._files_open.show_verdicts([])
        self._refresh_sections()
        self.update_status(
            counts={},
            planned=True,
            planning="",
            stale_edits=0,
            cost="",
            exposures=0,
            coverage=None,
            tests=None,
            blocked=outcome.failure or "The plan failed",
            problems=len(outcome.errors),
        )
        self._last_errors = outcome.errors
        self._last_warnings = outcome.warnings
        self._reviewed = False
        self._refresh_apply()
        self.plan_panel.failed(
            outcome.failure or "The plan failed",
            found=outcome.errors,
            warnings=outcome.warnings,
            on_show_output=lambda: self.show_output(outcome.output),
            source=self._source_of(outcome.diagnostics),
            on_open=self.open_at,
            on_fix=self.fix_and_replan,
        )
        self.open_drawer("Changes")
        if outcome.needs_initialising:
            # The first failure almost everybody meets, and one command fixes
            # it. Offering it is more use than repeating what the engine said.
            self._offer_to_initialise()

    def explain_backend(self, module: Module) -> None:
        """Opens the recovery view for a module keeping its state locally."""
        assert self.workspace is not None
        relative = module.path.relative_to(self.workspace.path).as_posix()
        BackendDialog(
            relative if relative not in ("", ".") else module.path.name,
            backend_state.local_state(module.path),
        ).present(self)

    def _source_of(self, found: list) -> dict[str, str]:
        """The current text of every file a diagnostic points at.

        Read from the open buffer where there is one, because that is what the
        person is looking at. A fix computed against the file on disk would be
        offered for a line they have already changed.
        """
        if self.workspace is None:
            return {}
        text: dict[str, str] = {}
        for diagnostic in found or []:
            if not diagnostic.path or diagnostic.path in text:
                continue
            where = (self.workspace.path / diagnostic.path).resolve()
            page = self._files_open.pages.get(where)
            if page is not None:
                buffer = page.buffer
                text[diagnostic.path] = buffer.get_text(
                    buffer.get_start_iter(), buffer.get_end_iter(), False
                )
                continue
            try:
                text[diagnostic.path] = where.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
        return text

    def open_at(self, path: str, line: int) -> None:
        """Opens the file a diagnostic named, with the caret on the line."""
        if self.workspace is None:
            return
        where = (self.workspace.path / path).resolve()
        if not where.is_file():
            self._still_true(f"{path} is not in this workspace any more")
            return
        self.open_file(where)
        page = self._files_open.current
        if page is not None:
            page.go_to_line(line)
            page.view.grab_focus()

    def fix_and_replan(self, diagnostic, repair) -> None:
        """Applies the one edit, saves, and plans again — as one undo.

        The buffer may have moved since the plan ran, so the line is checked
        against what is there now rather than trusted. A fix that lands on a
        line somebody has already changed is worse than no fix at all.
        """
        self.open_at(diagnostic.path, repair.line)
        page = self._files_open.current
        if page is None:
            return
        buffer = page.buffer
        found, start = buffer.get_iter_at_line(repair.line - 1)
        if not found:
            self._still_true("That line is no longer there")
            return
        end = start.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        if buffer.get_text(start, end, False) != repair.before:
            self._still_true("That line has changed since the plan ran")
            return
        buffer.begin_user_action()
        buffer.delete(start, end)
        buffer.insert(start, repair.after)
        buffer.end_user_action()
        # It is called "Fix and re-plan", so it re-plans — rather than saving
        # and leaving the second half of its own name to a setting.
        self.plan_now()
        self._say(repair.label)

    def _offer_to_initialise(self) -> None:
        """The blocking banner says it, so there is nothing separate to offer.

        It said the same thing twice from two places, which is how the two come
        to disagree about the wording.
        """
        self.show_what_is_blocking()

    def _on_progress(self, progress: Progress) -> None:
        if progress.stage is Stage.WAITING:
            self.plan_panel.waiting("Planning shortly…")
        elif progress.stage is Stage.RUNNING:
            self.plan_panel.waiting("Planning…")
            if not self._planning:
                self._planning = True
                self._planning_since = time.monotonic()
            self.update_status(planning=self._environment() or "this workspace")
        elif progress.stage is Stage.FAILED:
            self.plan_panel.failed(progress.detail or "The plan failed.")
        if progress.stage is not Stage.RUNNING:
            self._planning = False
            self.update_status(planning="")
        self._refresh_apply()

    def _on_plan(self, outcome: PlanOutcome) -> None:
        self._planning = False
        if outcome.plan is None:
            self._plan_failed(outcome)
            return
        # Warnings never stopped anything. They belong under the changes, not
        # in front of them: the person came for the plan.
        self._last_errors = []
        self._last_warnings = outcome.warnings
        self._reviewed = False
        verdicts = self._verdicts_for(outcome.plan)
        self._plan = outcome.plan
        self._planned_at = time.monotonic()
        self._plan_document = getattr(outcome, "document", None)
        # The artifact, not the configuration. Applying the configuration would
        # run whatever it says now, which is not what anybody reviewed.
        self._plan_artifact = outcome.artifact
        self._estimate_cost()
        self._refresh_sections()
        self._refresh_apply()
        self._files_open.show_verdicts(verdicts)
        self._files_open.show_hints(self._hints_for(outcome))
        self._show_lenses(outcome)
        self._refresh_statuses(outcome.plan)
        if self._plan_document is not None and self.settings.get("analysis.exposure_on_edit", True):
            self.exposure_panel.show(exposure.analyse(project(self._plan_document)))
        # Read from the same place the gate reads, or the status bar says apply
        # is impossible while the footer offers it — the one thing the design says
        # this window must never do. It was a hardcoded sentence.
        self._edits_since_the_plan = 0
        self._estimate_cost()
        self.cost_panel.show(self._cost, have_prices=self._prices.any)
        # The panel is drawn after the cost is known, so a row can say what it
        # costs as well as where it was written. Drawing it first meant the two
        # facts a reviewer needs most arrived a frame apart, and one of them
        # never arrived at all.
        self.plan_panel.show(
            outcome.plan,
            warnings=outcome.warnings,
            source_map=self._source_map(),
            estimate=self._cost,
        )
        cost_chip, cost_direction = self._cost.chip
        self.update_status(
            counts={action.value: count for action, count in outcome.plan.counts().items()},
            planned=True,
            planning="",
            stale_edits=0,
            problems=0,
            cost=cost_chip,
            cost_direction=cost_direction,
            blocked=(
                analysis_sections.why_apply_is_blocked(
                    outcome.plan, self._capabilities(), len(outcome.plan.changes)
                )
                or ""
            ),
        )

    def _show_lenses(self, outcome) -> None:
        """The code lens, from the plan document and where each block lives."""
        document = getattr(outcome, "document", None)
        if document is None or self.workspace is None or self.speculator is None:
            return
        module = self.workspace.module_at(self.speculator.directory)
        if module is None:
            return
        source_map = SourceMap.build(self.workspace, module)
        self._files_open.show_lenses(lens_source.for_plan(document, source_map), source_map)

    def _hints_for(self, outcome) -> list:
        """Resolved values and expansion, read from the plan document."""
        document = getattr(outcome, "document", None)
        if document is None or self.workspace is None or self.speculator is None:
            return []
        module = self.workspace.module_at(self.speculator.directory)
        if module is None:
            return []
        return hint_source.for_plan(document, SourceMap.build(self.workspace, module))

    def _verdicts_for(self, plan) -> list:
        """Where each change in the plan was written."""
        if self.workspace is None or self.speculator is None:
            return []
        module = self.workspace.module_at(self.speculator.directory)
        if module is None:
            return []
        return for_plan(plan, SourceMap.build(self.workspace, module))

    def open_workspace(self, path: Path) -> None:
        """Reads a directory and shows what is in it."""
        if self.speculator is not None:
            self.speculator.cancel()
        self.workspace = discover(path)
        if self.settings.get("layout.remember_per_workspace"):
            kept = remembered.layout_for(path)
            if kept is not None:
                self.layout = kept
                for name in self._panels:
                    self._apply(name)

        self._show_files()
        self._show_the_right_nothing()
        self.refresh_stacks()
        self.refresh_switcher()
        self._show_providers()
        self.refresh_vcs()
        self.update_status(
            branch=self._vcs.branch or "",
            language="HCL",
            state="" if self._has_a_backend() else blocking.LOCAL_STATE,
            planned=False,
            counts=None,
            blocked="",
            problems=0,
            cost=None,
            exposures=None,
            coverage=None,
            tests=None,
            drifted=None,
            stale_edits=0,
        )

        if self.speculator is not None:
            self.speculator.cancel()
            self.speculator = None
        self.plan_panel.waiting(
            "Open a file to plan its module" if self.workspace.is_terraform else "No Terraform here"
        )
        self._drift = drifting.Drift()
        self.drift_panel.show(self._drift)
        self._refresh_drift_rail()
        self._start_watching_for_drift()
        self.load_library()
        self.read_credentials()
        self.show_workspace_heading()
        self.show_what_is_blocking()
        if self.settings.get("session.restore", True):
            self.restore_session()
        self._say_if_the_engine_is_missing()
        self.refresh_git_panel()
        self._fold_when_there_is_no_room()

    def _buffer_touched(self, page) -> None:
        self._plan_went_stale()
        self.buffer_changed(page)

    def check_files_on_disk(self) -> None:
        """Whether anything open changed underneath us, and what to do about it.

        Run when the window is focused again, which is when a branch switch or
        a `fmt` in a terminal has just happened. An unmodified buffer is
        reloaded without asking — there is nothing to lose and nothing to
        decide. A modified one is never overwritten silently.
        """
        gone, clashing = [], []
        for path, page in list(self._files_open.pages.items()):
            what = watching.what_happened(page.stamp, path)
            if what == watching.Change.NOTHING:
                continue
            if what == watching.Change.DELETED:
                gone.append(page)
                page.stamp = watching.Stamp.of(path)
                continue
            if not page.modified:
                page.reload_from_disk()
                continue
            clashing.append(page)
        if gone:
            self._still_true(_deleted_underneath(gone))
        if clashing:
            self._offer_to_reload(clashing)

    def _offer_to_reload(self, pages: list) -> None:
        """Both versions exist and only one can stay. It is not ours to pick.

        One offer for all of them rather than one per file: these arrive
        together — a branch switch or a `fmt` in a terminal touches several —
        and a stack of permanent notices is a stack nobody reads.
        """
        self._still_true(
            _changed_underneath(pages),
            action="Reload" if len(pages) == 1 else "Reload all",
            then=lambda: [self._reload(page) for page in pages],
        )
        # Stamped as seen, so the same file does not ask again on every focus.
        for page in pages:
            page.stamp = watching.Stamp.of(page.path)

    def _reload(self, page) -> None:
        page.reload_from_disk()
        recovery.drop(page.path)
        self._say(f"{Path(page.path).name} reloaded from disk")

    def buffer_changed(self, page) -> None:
        """Sets the buffer aside, and saves it where that is asked for."""
        if page.modified:
            recovery.keep(page.path, page.text())
        if self.settings.get("editor.autosave", False) and page.modified:
            self.save_current()

    def offer_what_was_left_behind(self) -> None:
        """What an unclean exit left, offered once at launch.

        Anything matching what is already on disk is dropped without a word: a
        prompt about nothing is how people learn to dismiss the prompt.
        """
        found = [entry for entry in recovery.waiting() if recovery.is_still_different(entry)]
        for stale in recovery.waiting():
            if stale not in found:
                recovery.drop(stale.path)
        if not found:
            return
        self._still_true(
            f"{len(found)} file{'' if len(found) == 1 else 's'} had unsaved changes "
            "when the application last closed",
            action="Recover",
            then=lambda f=found: self.recover(f),
        )

    def recover(self, found: list) -> None:
        """Opens each one and puts the unsaved text back, unsaved.

        Nothing is written. Recovering shows somebody their work; whether it
        belongs in the file is theirs to decide.
        """
        for entry in found:
            if not entry.path.parent.is_dir():
                continue
            if entry.path.is_file():
                self.open_file(entry.path)
            page = self._files_open.current
            if page is None or page.path != entry.path:
                continue
            page._replace_keeping_the_caret(entry.text)
            page.buffer.set_modified(True)
        self._say("Recovered. Nothing was written — save what you want to keep.")

    def closing(self) -> None:
        """Everything worth keeping, written once on the way out.

        Never allowed to stop the window closing: losing a layout is a lost
        layout, and an exception here would be a shutdown somebody has to kill.
        """
        # A clean exit means nothing was lost, so nothing is left waiting.
        recovery.drop_everything()
        for keep in (self.remember_geometry, self.remember_session, self._remember_layout):
            try:
                keep()
            except Exception as failed:  # noqa: BLE001
                # Said out loud rather than swallowed. The window is going, so
                # there is nowhere on screen left to say it.
                print(f"backsight: could not save {keep.__name__}: {failed}", file=sys.stderr)

    def restore_session(self) -> None:
        """Reopens what was open here, with the caret where it was left.

        A file that has since gone is skipped in silence. Being told about four
        deleted files every morning is a worse start than not being returned to
        them.
        """
        if self.workspace is None:
            return
        found = session.read_session(self.workspace.path)
        if found.is_empty:
            return
        opened = []
        for entry in found.files:
            where = (self.workspace.path / entry.path).resolve()
            if not where.is_file():
                continue
            self.open_file(where)
            page = self._files_open.current
            if page is not None:
                page.go_to_line(entry.line)
                opened.append((entry, page))
        for entry, page in opened:
            if entry.path == found.active:
                self._files_open.open(page.path)

    def remember_session(self) -> None:
        """Records what is open, so the next launch returns here."""
        if self.workspace is None or not self.settings.get("session.restore", True):
            return
        files = []
        for path, page in self._files_open.pages.items():
            try:
                relative = (
                    Path(path).resolve().relative_to(self.workspace.path.resolve()).as_posix()
                )
            except ValueError:
                continue
            caret = page.buffer.get_iter_at_mark(page.buffer.get_insert())
            files.append(
                session.OpenFile(
                    path=relative, line=caret.get_line() + 1, column=caret.get_line_offset()
                )
            )
        here = self._files_open.current
        active = ""
        if here is not None:
            try:
                active = (
                    Path(here.path).resolve().relative_to(self.workspace.path.resolve()).as_posix()
                )
            except ValueError:
                active = ""
        session.remember_session(self.workspace.path, session.Session(files=files, active=active))

    def remember_geometry(self) -> None:
        """Records the window, which belongs to this machine rather than a workspace."""
        width, height = self.get_default_size()
        session.remember_geometry(
            session.Geometry(
                width=max(width, 1),
                height=max(height, 1),
                maximised=self.is_maximized(),
                sidebar=self._outer.get_position() if self._outer is not None else 240,
            )
        )

    def open_stack(self, stack) -> None:
        """Opens a stack's directory in the file rail, without leaving here."""
        if self.workspace is None:
            return
        where = self.workspace.path / stack.path
        found = sorted(where.glob("*.tf")) if where.is_dir() else []
        if not found:
            self._say(f"{stack.name} declares {stack.path}, which has no Terraform in it")
            return
        self.open_file(found[0])

    def refresh_stacks(self) -> None:
        """Re-reads the stack file and shows the radius of what is open.

        The radius is of the whole stack rather than of this edit: knowing
        which outputs a change touches needs a plan, and the rail is useful
        before there is one.
        """
        if self.workspace is None:
            self.stacks = stack_model.Definitions()
            self.stacks_rail.show(self.stacks)
            return
        self.stacks = stack_model.read(self.workspace.path)
        page = self._files_open.current
        editing = self.stacks.containing(page.path) if page is not None else None
        radius = (
            stack_graph.consumers_of(self.stacks, editing.name) if editing is not None else None
        )
        self.stacks_rail.show(self.stacks, radius)
        self._title_the_stack(editing)
        self._refresh_stack_freshness()

    def _title_the_stack(self, stack) -> None:
        """The design puts the stack and its region in the header.

        Which account a change is aimed at is the fact worth having in front of
        you at all times. It is left out entirely when the stack does not say,
        because a plausible guess there is how somebody applies to the wrong
        account while reading a header that told them otherwise.
        """
        if stack is None:
            return
        self._switcher.show(self._known_workspace(), self._known)

    def _show_files(self) -> None:
        """Points the tree at the workspace, or filters what is in it.

        **It is not rebuilt on a refresh.** A tree that is rebuilt every time a
        plan finishes is a tree that closes under you, and what somebody has
        opened is the only state in the rail worth anything. Marks are asked
        for per row instead — see `FileTree.remark`.
        """
        workspace = self.workspace
        if workspace is None:
            self._files.show(None)
            self._rail_hidden.set_visible(False)
            return
        if workspace.path != self._rail_root:
            self._rail_root = workspace.path
            self._files.show(workspace.path)
        self._filter_the_tree()

    def _filter_the_tree(self) -> None:
        """Reveals what matches, rather than hiding what does not.

        **Filtering a tree that has not been read is a contradiction**: hiding
        a row means knowing about every row, which means walking the whole
        repository — the cost the tree exists to avoid. So a filter opens the
        ancestors of everything that matches and says how many there were, and
        the rest of the tree stays where it was, collapsed.
        """
        term = self._rail_filter.get_text() if self._rail_filter.get_visible() else ""
        if not term.strip():
            self._rail_hidden.set_visible(False)
            return
        found = tree.matching(self._rail_root, term) if self._rail_root else []
        for path in found[: self.REVEALS]:
            self._files.reveal(path)
        if found:
            self._files.reveal(found[0])
        self._rail_hidden.set_label(_matched(len(found), self.REVEALS))
        self._rail_hidden.set_visible(True)

    def _marks_for(self, path: Path, is_dir: bool) -> tuple[str, str]:
        """What one row says on its right, and what colour its left edge takes.

        Asked by the tree as each row is drawn, so a plan finishing costs a
        redraw rather than a rebuild.

        **A directory carries the sum of what is under it** — which is the one
        thing a collapsed row has to be able to answer, and the only reason to
        put a number on a folder at all. It says nothing when there is nothing.
        """
        counts = bool(self.settings.get("rail.indicators.plan_counts", True))
        shape = str(self.settings.get("rail.indicators.vcs", "letter"))
        if is_dir:
            if not counts:
                return "", ""
            inside = [
                status
                for where, status in self._statuses.items()
                if status.shows_impact and status.summary and _inside(where, path)
            ]
            return (file_status.combined(inside) if inside else "", "")
        status = self._statuses.get(Path(path).resolve())
        if status is None:
            return "", ""
        edge = ""
        if shape != "none" and status.vcs.letter:
            edge = VCS_CLASSES.get(status.vcs.letter, "tf-git-changed")
        said = status.summary if (counts and status.shows_impact) else ""
        return said or "", edge

    def _menu_for(self, path: Path, is_dir: bool) -> Gio.Menu:
        """The menu for whatever the pointer is on."""
        return self._folder_menu_for(path) if is_dir else self._file_menu(path)

    def _folder_menu_for(self, path: Path) -> Gio.Menu:
        """A folder's menu. The Workspace section is absent unless it is a root."""
        module = self.workspace.module_at(path) if self.workspace else None
        traits = ["root_module"] if module is not None and module.is_root else []
        return context_menu.to_model(FOLDER_CONTEXT_MENU.given(*traits), self.keymap)

    def _file_menu(self, path: Path) -> Gio.Menu:
        """A file's menu, for the file it is actually on."""
        traits = []
        if path.suffix == ".tf" or path.name.endswith(".tftest.hcl"):
            traits.append("terraform")
        if self._vcs.tracks(path):
            traits.append("tracked")
        return context_menu.to_model(FILE_CONTEXT_MENU.given(*traits), self.keymap)

    def _clicked(self, path: Path, presses: int) -> None:
        """What a click on a file in the rail does. **One click previews, two open.**

        A preview shows the file in the view in front of you and the next one
        replaces it, so looking through a repository leaves no tab per click.
        A double click opens the file for good. Where *Open a file from the
        rail with* says a single click, one click is enough to open it.
        """
        one_opens = self.settings.get("files.open_on", "double_click") == "single_click"
        if presses < 2 and not one_opens:
            self.open_file(path, preview=True)
            return
        # A file already previewed is the one that opens: it is focused rather
        # than opened twice, and stops being the preview.
        self.open_file(path, preview=False)
        self._files_open.promote(path)

    def open_file(self, path: Path, *, preview: bool | None = None) -> None:
        """Shows a file, reusing the tab you are in unless told otherwise.

        **Opening replaces; a new tab is a deliberate choice.** Twenty files
        looked at is twenty tabs to close otherwise, and it was every open
        rather than only browsing — so a definition you followed, a palette
        result and a click in the rail all left one behind.

        The tab is only reused while nothing has been typed in it: an edit
        promotes it, so a file somebody has changed is never replaced under
        them. `preview=False` is for the places where a second tab is the
        point — Open in a new tab, reopening a closed one, and the far pane of
        a split.
        """
        reusing = bool(self.settings.get("files.preview_tabs", True))
        wanted = reusing if preview is None else preview
        try:
            self._files_open.open(path, preview=wanted)
        except NotUtf8 as refused:
            # Refusing is the correct outcome, so it is reported in the window
            # rather than raised into a traceback nobody sees.
            self._still_true(str(refused))
            return
        self.dismiss_banner()
        self._editor.set_visible_child_name("file")
        # A test file shows the shape of its runs at once. With no results yet
        # every run is pending, which is a state rather than an absence.
        if Path(path).name.endswith(".tftest.hcl") and self.workspace is not None:
            self._files_open.show_test_results(self._last_results, self.workspace.path)
        self.refresh_stacks()
        self._mark_the_current_file(path)
        self._reveal_in_rail(path)
        module = self._module_for(Path(path).resolve())
        if module is not None:
            self._watch(module)
        page = self._files_open.current
        if page is not None:
            page.buffer.connect("changed", lambda *_a, p=page: self._buffer_touched(p))
        self._refresh_statuses()

    def _say(self, message: str) -> None:
        """For something that has finished. A toast expires; use it for events."""
        self.activity.append(message)
        toast = Adw.Toast(title=message, timeout=8)
        self._toasts.add_toast(toast)

    def show_what_is_blocking(self) -> None:
        """The one condition stopping this workspace, across the top.

        It was a truncated red line at the bottom of the window, cut off
        mid-word — the least prominent place on screen for the thing nothing
        works without. The status bar keeps a short version.
        """
        found = blocking.first(
            # Asked rather than read: the field is None before anything has
            # looked, which is a different thing from the engine being absent.
            engine_missing=not self._engine_version(),
            initialised=self._is_initialised(),
        )
        # Local state is not a banner. It is a standing fact, so it goes in the
        # strip that carries the other standing facts about this workspace.
        self.update_status(state="" if self._has_a_backend() else blocking.LOCAL_STATE)
        self._blocking = found
        if found is None:
            if self._banner_is_blocking:
                self._banner_is_blocking = False
                self.dismiss_banner()
            return
        self._banner_is_blocking = True
        self._banner.set_title(found.title + " — " + found.body)
        self._banner.set_button_label(found.action)
        self._banner_action = lambda: self.activate_action(f"win.{found.command}", None)
        self._banner.set_revealed(True)

    def _is_initialised(self) -> bool:
        """Whether `.terraform` is there, which is what init leaves behind."""
        if self.workspace is None or self.speculator is None:
            return True
        return (self.speculator.directory / ".terraform").is_dir()

    def _has_a_backend(self) -> bool:
        if self.workspace is None:
            return True
        return any(module.backend for module in self.workspace.root_modules)

    def _still_true(self, message: str, *, action: str = "", then=None) -> None:
        """For something that is still the case.

        The second critical fix: a toast is for a thing that has
        finished, not a thing that is still true. A file that cannot be read is
        still unreadable four seconds later, and a message that has gone leaves
        somebody looking at a blank tab with no explanation.

        `action` puts the thing to do about it on the banner. Three of these
        were toasts with `timeout=0`, which is a banner wearing a toast's
        clothes: it sat over the window forever, in the corner, with no way to
        tell it apart from the four-second one that had just been there.
        """
        self._banner.set_title(message)
        self._banner.set_button_label(action or "Dismiss")
        self._banner_action = then
        self._banner.set_revealed(True)

    def _banner_clicked(self) -> None:
        """Whatever this banner offered, or dismissing it when it offered nothing."""
        then, self._banner_action = self._banner_action, None
        self.dismiss_banner()
        if then is not None:
            then()

    def dismiss_banner(self) -> None:
        """Puts the banner away, unless what it says is still blocking.

        Dismissing "this workspace has not been initialised" would hide the
        reason nothing works.
        """
        if self._blocking is not None and not self._blocking.dismissible:
            return
        self._blocking = None
        self._banner_is_blocking = False
        self._banner_action = None
        self._banner.set_button_label("Dismiss")
        self._banner.set_revealed(False)

    def _show_providers(self) -> None:
        """Which provider version is actually in use, for the file in front of you.

        **The module, not the repository.** Every root module in a library
        locks its own providers, so asking all twenty-seven produced a line
        reading `aws 6.64.0, local 2.9.0, random 3.9.0, random 3.9.0, tls 4…`
        — the same provider twice, because two of them locked it from
        different sources, and a list too long to fit whatever it said.

        The file facts are facts about the file. With nothing open there is no
        module to ask, so the workspace answers instead.
        """
        workspace = self.workspace
        if workspace is None:
            self._providers = []
            self.update_status(provider="")
            return
        here = self._files_open.current
        module = workspace.module_at(here.path.parent) if here is not None else None
        asking = [module] if module is not None else list(workspace.root_modules)
        locked = sorted(
            {
                (p.name, p.locked_version, p.source)
                for m in asking
                for p in m.providers
                if p.locked_version
            }
        )
        self._providers = locked
        # A provider locked at one version from two sources is one fact. Two
        # versions of one provider is two, and worth seeing.
        said = sorted({(name, version) for name, version, _source in locked})
        self.update_status(provider=", ".join(f"{name} {version}" for name, version in said))
        self._check_provider_versions()

    def _check_provider_versions(self) -> None:
        """Asks a registry whether any of them is behind, when told to.

        Off the main loop and never blocking anything: the versions on screen
        are already true, and this only ever adds a phrase beside one of them.
        Not knowing is left as not knowing.
        """
        if not self.settings.get("analysis.check_provider_versions", False):
            return
        wanted = list(self._providers)
        if not wanted:
            return

        def finished(behind: list[str]) -> None:
            if not behind:
                return
            said = ", ".join(behind)
            self.update_status(provider=f"{self._status_facts.get('provider', '')} · {said}")

        def work() -> None:
            found = []
            for name, version, source in wanted:
                answer = self._versions.check(name, installed=version, source=source)
                if answer.is_behind:
                    found.append(f"{name} {answer.summary}")
            on_main_loop(finished)(found)

        threading.Thread(target=work, name="backsight-versions", daemon=True).start()

    # --- panels, and getting them back --------------------------------------

    def register_panel(self, name: str, widget: Gtk.Widget) -> None:
        """Says this window actually has that panel, and shows it accordingly."""
        self._panels[name] = widget
        self._apply(name)

    def peek(self, name: str) -> None:
        """Shows a hidden panel for a moment without changing the layout.

        FR-APP-35. Pressing a hidden panel's key to check one thing and having
        to press it again to put it back is the layout arguing with somebody
        who only wanted to look. Escape ends it, and the saved layout never
        moved — so nothing has to be undone.
        """
        if self.layout.is_shown(name):
            self.toggle_panel(name)
            return
        self._peeking = name
        widget = self._panels.get(name)
        if widget is not None:
            widget.set_visible(True)
        if name == "left_rail":
            self._rail_scroller.set_visible(True)
            self._rail_strip.set_visible(False)
            self._outer.set_position(self._geometry.sidebar)
        if name == "plan_drawer":
            self._size_drawer()
        self._say(f"{name.replace('_', ' ')} — Escape to put it back")

    def stop_peeking(self) -> bool:
        """Puts back whatever was being looked at. False when nothing was."""
        name, self._peeking = self._peeking, ""
        if not name:
            return False
        self._apply(name)
        return True

    def keep_peeked(self) -> None:
        """What a pin does: the thing being looked at stays."""
        name, self._peeking = self._peeking, ""
        if name:
            self.show_panel(name)

    def toggle_panel(self, name: str) -> None:
        """The everyday toggle, on a key.

        A collapsible rail goes between shown and collapsed and never reaches
        hidden — a strip costs eight pixels and means a mis-hit key never loses
        a feature outright. Hiding is a deliberate act, from the menu.
        """
        self.layout.toggle(name)
        self._apply(name)
        self._remember_layout()

    def hide_panel(self, name: str) -> None:
        """Unchecking it in the menu.

        Nothing is said about it. A hidden panel is visibly gone and comes back
        with the same key, and a toast offering to undo it treats a view toggle
        as a destructive act — which is how people learn to dismiss toasts
        without reading them, including the one saying an apply finished.
        """
        if not self.layout.is_shown(name):
            return
        self.layout.set(name, Visibility.HIDDEN)
        self._apply(name)
        self._remember_layout()

    def show_panel(self, name: str) -> None:
        self._folded.discard(name)
        self.layout.set(name, Visibility.SHOWN)
        self._apply(name)
        self._remember_layout()

    def set_panel_shown(self, name: str, shown: bool) -> None:
        """What the menu's checkmark does."""
        self.show_panel(name) if shown else self.hide_panel(name)

    def _fold_at_every_width(self) -> None:
        """A breakpoint, so the folding happens on resize rather than once."""
        for needed in (self.FOLD_RAIL,):
            point = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(f"max-width: {needed - 1}px"))
            point.connect("apply", lambda *_: self._fold_when_there_is_no_room())
            point.connect("unapply", lambda *_: self._fold_when_there_is_no_room())
            self.add_breakpoint(point)

    def _fold_when_there_is_no_room(self, room: int | None = None) -> None:
        """Puts the side panels away when the window is too narrow to hold them.

        Below its own minimum the window does not scroll or reflow, it clips —
        so at 630px a panel's text ran off the right edge of the screen. What is
        folded here is never written to the layout file, so widening the window
        brings back exactly what was chosen.
        """
        room = self.get_width() if room is None else room
        if room <= 0:
            return
        for name, needed in (("left_rail", self.FOLD_RAIL),):
            crowded = room < needed
            if crowded and self.layout.is_shown(name):
                self._folded.add(name)
                self.hide_panel(name)
            elif not crowded and name in self._folded:
                self._folded.discard(name)
                self.show_panel(name)

    def reset_layout(self) -> None:
        """The universal escape from any configuration somebody got into."""
        self.layout.reset()
        for name in self._panels:
            self._apply(name)
        # Reset means reset: a remembered layout that survived it would come
        # back on the next open and the escape hatch would not have worked.
        if self.workspace is not None:
            remembered.forget(self.workspace.path)

    def show_keyboard_reference(self) -> None:
        KeyboardReference(self.keymap, parent=self).present()

    def rebind(self, action: str, accelerator: str | None) -> None:
        """Changes one binding, and reports a refusal rather than swallowing it.

        The two keys everything else is reached through cannot be unbound; the
        keymap says so and this passes the message on.
        """
        try:
            self.keymap = Keymap.build({**self._overrides(), action: accelerator})
        except (Unbindable, KeyError) as refused:
            self._say(str(refused))
            return
        self._overridden[action] = accelerator
        self._menu_titles.set_menu_model(menu_bar.model(self.keymap))
        self._hamburger.set_menu_model(menu_bar.everything(self.keymap, bar_shown=False))
        for conflict in self.keymap.conflicts():
            self._say(str(conflict))

    def _overrides(self) -> dict[str, str | None]:
        return dict(self._overridden)

    def show_palette(self, prefix: str = "") -> None:
        """Opens the palette, already filtered to what the key asked for."""
        palette = Palette(
            self._palette_entries(),
            self._palette_suggestions(),
            parent=self,
            on_choose=self._on_palette_choice,
        )
        palette.entry.set_text(prefix)
        palette.entry.set_position(-1)
        palette.present()

    def _palette_entries(self) -> list[palette_source.Entry]:
        """Everything reachable, from what is already parsed.

        Resource addresses cost nothing to offer: the parser knows them all
        because it built the source map to answer other questions.
        """
        found: list[palette_source.Entry] = []
        if self.workspace is not None:
            for module in self.workspace.modules:
                for path in module.files:
                    found.append(
                        palette_source.Entry(
                            label=path.relative_to(self.workspace.path).as_posix(),
                            kind=palette_source.Kind.FILE,
                        )
                    )
            for module in self.workspace.modules:
                source_map = SourceMap.build(self.workspace, module)
                for address, where in source_map.places.items():
                    found.append(
                        palette_source.Entry(
                            label=address,
                            kind=palette_source.Kind.RESOURCE,
                            detail=f"{where.path}:{where.line}",
                        )
                    )
        # **Every menu item, not only the ones with a key.** The palette offered
        # `self.keymap.commands` — so a command reachable from a menu and bound
        # to nothing was reachable from *no* keyboard at all, and the design's
        # own rule is that anything not on the keyboard reference is in the
        # palette and nothing is only in a menu.
        #
        # A blocked item is left out: it says why on its own row in the menu,
        # and a palette result that cannot run is a result that wastes a choice.
        for label, action in self._every_command():
            found.append(
                palette_source.Entry(
                    label=label,
                    kind=palette_source.Kind.COMMAND,
                    action=action,
                    detail=pretty_key(self.keymap.accelerator(action) or "") or "",
                )
            )
        found.extend(self._palette_problems())
        return found

    def _palette_problems(self) -> list[palette_source.Entry]:
        """Everything stopping this plan, and everything the policy found.

        The same two lists the verdict line counts and the Changes panel draws,
        so the palette cannot disagree with either about what is wrong.
        """
        found: list[palette_source.Entry] = []
        for problem in (*self._last_errors, *self._last_warnings):
            where = str(getattr(problem, "path", "") or "")
            line = int(getattr(problem, "line", 0) or 0)
            said = str(getattr(problem, "summary", "") or getattr(problem, "message", "") or "")
            if not said:
                continue
            found.append(
                palette_source.Entry(
                    label=said,
                    kind=palette_source.Kind.PROBLEM,
                    detail=f"{where}:{line}" if where and line else "",
                    # Above a policy finding: an error stops the plan and a
                    # finding does not.
                    weight=1 if problem in self._last_errors else 0,
                )
            )
        for finding in self._policy.findings:
            where = str(getattr(finding, "path", "") or "")
            line = int(getattr(finding, "line", 0) or 0)
            said = str(getattr(finding, "title", "") or getattr(finding, "summary", "") or "")
            if said:
                found.append(
                    palette_source.Entry(
                        label=said,
                        kind=palette_source.Kind.PROBLEM,
                        detail=f"{where}:{line}" if where and line else "",
                    )
                )
        return found

    def _every_command(self) -> list[tuple[str, str]]:
        """Every command a person can reach by pointing, each named once.

        The menus first, because their labels are the words somebody has
        already read; the keymap second, for anything bound to a key and in no
        menu. First name wins, so a command does not appear twice under two
        spellings.
        """
        found: dict[str, str] = {}
        for menu in EVERY_ENTRY_POINT:
            for item in menu.items():
                if item.action and not item.blocked_because and item.action not in found:
                    found[item.action] = item.label
        for command in self.keymap.commands.values():
            found.setdefault(command.action, command.label)
        return [(label, action) for action, label in found.items()]

    def _palette_suggestions(self) -> list[palette_source.Entry]:
        """What to offer before anything is typed. Never nothing.

        What somebody reached for last comes first: a fixed list answers "I do
        not know what this can do" once, and what they actually use answers it
        every time after.
        """
        found = []
        wanted = recents.read()
        for action in [*wanted, *[one for one in SUGGESTED_COMMANDS if one not in wanted]]:
            command = self.keymap.commands.get(action)
            if command is None:
                continue
            found.append(
                palette_source.Entry(
                    label=command.label,
                    kind=palette_source.Kind.COMMAND,
                    action=command.action,
                    detail=pretty_key(command.accelerator) if command.accelerator else "",
                )
            )
        return found

    def _on_palette_choice(self, entry: palette_source.Entry) -> None:
        """Acts on what was chosen, by the kind it is."""
        if entry.kind is palette_source.Kind.COMMAND and entry.action:
            recents.remember(entry.action)
        if entry.kind is palette_source.Kind.FILE and self.workspace is not None:
            self.open_file(self.workspace.path / entry.label)
            return
        if entry.kind in (palette_source.Kind.RESOURCE, palette_source.Kind.PROBLEM):
            self._go_to(entry.detail)
            return
        if entry.kind is palette_source.Kind.LINE:
            self._go_to_line(int(entry.label.split()[-1]))
            return
        if entry.action:
            self.activate_action(f"win.{entry.action}", None)

    def _go_to(self, where: str) -> None:
        """Opens `path:line`, which is how a resource says where it lives."""
        path, _, line = where.rpartition(":")
        if not path or not line.isdigit() or self.workspace is None:
            return
        self.open_file(self.workspace.path / path)
        self._go_to_line(int(line))

    def _go_to_line(self, line: int) -> None:
        page = self._files_open.current
        if page is None:
            return
        page.go_to_line(line)

    def validate_workspace(self) -> None:
        """Asks the engine whether the configuration holds together."""
        self._in_the_background(
            "Validating…",
            lambda directory: engine_commands.validate(directory),
            self._validated,
        )

    def _validated(self, answer) -> None:
        self._say(answer.summary())
        if answer.valid or not answer.errors:
            self.dismiss_banner()
            return
        first = answer.errors[0]
        where = f" ({first.where})" if first.where else ""
        # A validation error is still true after a toast has gone, so it goes
        # in the banner rather than out of the corner of your eye.
        self._still_true(f"{first.summary}{where} — {first.detail}")

    def _resync_view_ticks(self) -> None:
        """Puts every checkable View item back in step with the setting it shows.

        A tick that disagrees with the buffer is the defect this replaced two
        actions to fix, and it comes straight back if Preferences can change a
        setting without the menu hearing about it.
        """
        for name, key in self._view_toggles.items():
            action = self.lookup_action(name)
            if action is not None:
                action.set_state(GLib.Variant.new_boolean(bool(self.settings.get(key, False))))

    def toggle_view(self, key: str) -> None:
        """Flips one editor display setting, and writes it down.

        A toggle that lasts until the next launch is a toggle somebody has to
        find again every morning.
        """
        now = not bool(self.settings.get(key, False))
        try:
            writing.remember(key, now)
        except (OSError, ValueError) as refused:
            self._still_true(f"Could not save that: {refused}")
            return
        self.settings_changed(key, now)

    def toggle_distraction_free(self) -> None:
        """Everything but the file goes away, and comes back the same way.

        What was showing before is remembered, so leaving it restores the
        layout somebody had rather than a default one.
        """
        if self._before_distraction_free is None:
            self._before_distraction_free = {
                name: self.layout.visibility(name) for name in self._panels
            }
            for name in self._panels:
                self.layout.set(name, Visibility.HIDDEN)
                self._apply(name)
            self._say("Distraction free — the same key brings it all back")
            return
        for name, was in self._before_distraction_free.items():
            self.layout.set(name, was)
            self._apply(name)
        self._before_distraction_free = None

    @property
    def is_distraction_free(self) -> bool:
        return self._before_distraction_free is not None

    def format_open_file(self) -> None:
        """Runs `fmt` on the buffer in front, as one undoable change.

        Off the drawing thread, because it is a subprocess. A file that will not
        parse is left exactly as it is and the engine says why — formatting is
        the one operation nobody expects to change what their code means.
        """
        page = self._files_open.current
        if page is None:
            return
        text = page.buffer.get_text(page.buffer.get_start_iter(), page.buffer.get_end_iter(), True)
        binary = str(self.settings.get("terraform.binary", "tofu"))
        directory = page.path.parent

        def work() -> object:
            return engine_commands.format_text(text, directory=directory, binary=binary)

        def finished(answer) -> None:
            if answer is None or not answer.ok:
                self._still_true(
                    _one_line(answer.complaint) if answer is not None else "Formatting failed"
                )
                return
            if not answer.changed_anything:
                return
            here = self._files_open.current
            if (
                here is not page
                or page.buffer.get_text(
                    page.buffer.get_start_iter(), page.buffer.get_end_iter(), True
                )
                != text
            ):
                # Somebody typed while it ran. Their text wins.
                return
            page._replace_keeping_the_caret(answer.text)

        self._off_the_drawing_thread(work, finished)

    def format_workspace(self) -> None:
        """Says what formatting would change. It never changes it.

        Round-trip safety is a hard constraint, so reformatting somebody's
        files because they opened a menu is not on offer.
        """
        self._in_the_background(
            "Checking formatting…",
            lambda directory: engine_commands.formatting(directory),
            lambda answer: self._say(answer.summary()),
        )

    def initialise_workspace(self) -> None:
        self._in_the_background(
            "Initialising…",
            lambda directory: engine_commands.initialise(directory),
            self._initialised,
        )

    def _initialised(self, result) -> None:
        self.show_what_is_blocking()
        if result is None:
            self._still_true("Initialising did not finish")
            return
        self.show_output(result.out + result.err)
        self._say("Initialised" if result.ok else "Initialising failed")

    def _off_the_drawing_thread(self, work, finished) -> None:
        """Runs something slow and hands the answer back on the main loop.

        Says nothing on its own. `_in_the_background` announces what it is
        doing, which is right for a command somebody chose and wrong for one
        that runs on every save.
        """

        def run() -> None:
            on_main_loop(finished)(work())

        threading.Thread(target=run, name="backsight-format", daemon=True).start()

    def _in_the_background(self, saying: str, work, finished) -> None:
        """Runs an engine command off the main loop and reports on it.

        Everything here talks to a subprocess, so none of it may run on the
        thread that draws.
        """
        if self.workspace is None:
            self._say("Open a workspace first")
            return
        directory = self.workspace.path
        self._say(saying)

        def run() -> None:
            answer = work(directory)
            on_main_loop(finished)(answer)

        threading.Thread(target=run, name="backsight-engine", daemon=True).start()

    def _finding_here(self):
        """The verdict on the caret's line, and the address it is about."""
        page = self._files_open.current
        if page is None:
            return None
        buffer = page.buffer
        line = buffer.get_iter_at_mark(buffer.get_insert()).get_line()
        return page.marks.verdict_at(line)

    def explain_the_finding_on(self, line: int) -> None:
        """A click on a gutter mark. The line is the renderer's, counting from
        nought, and everything else here counts from one."""
        page = self._files_open.current
        if page is None:
            return
        page.go_to_line(line + 1)
        self.explain_finding()

    def finding_menu_at(self, line: int, x: float, y: float) -> None:
        """A right-click on a gutter mark, on the finding it is about.

        `GUTTER_MENU` has been declared since the menus were written and was
        attached to nothing, so the five things you can do about a finding were
        reachable from no pointer at all.
        """
        page = self._files_open.current
        if page is None:
            return
        page.go_to_line(line + 1)
        verdict = page.marks.verdict_at(line)
        traits = ["policy"] if verdict is not None and verdict.tone == "hint" else []
        if verdict is not None and verdict.tone == "exposure":
            traits.append("exposure")
        popover = Gtk.PopoverMenu.new_from_model(
            context_menu.to_model(GUTTER_MENU.given(*traits), self.keymap)
        )
        popover.set_parent(page.view)
        popover.set_has_arrow(False)
        where = Gdk.Rectangle()
        where.x, where.y, where.width, where.height = int(x), int(y), 1, 1
        popover.set_pointing_to(where)
        popover.connect("closed", lambda one: GLib.idle_add(one.unparent))
        popover.popup()

    def explain_finding(self) -> None:
        """Says what the mark on this line means, in the words the plan used."""
        verdict = self._finding_here()
        if verdict is None:
            self._say("No finding on this line")
            return
        self._still_true(f"{verdict.address} — {verdict.text}")

    def show_reachability(self) -> None:
        """The path from the internet to the resource on this line.

        It is the evidence for the claim, so a reviewer can disagree with it
        rather than take it on trust — FR-EXP-06.
        """
        verdict = self._finding_here()
        if verdict is None:
            self._say("No finding on this line")
            return
        if self._plan_document is None:
            self._say("Needs a plan to trace reachability")
            return
        report = exposure.analyse(project(self._plan_document))
        for finding in report.findings:
            if finding.address == verdict.address:
                self.exposure_panel.show(report)
                self.open_drawer(EXPOSURE)
                return
        self._say(f"The exposure analysis says nothing about {verdict.address}")

    def suppress_finding(self) -> None:
        """Hides a finding until a date. There is no way to hide one forever."""
        verdict = self._finding_here()
        if verdict is None or self.workspace is None:
            self._say("No finding on this line")
            return
        self.ask_for_a_name(
            "Suppress for how many days?", lambda days: self._suppress(verdict, days)
        )

    def _suppress(self, verdict, days: str) -> None:
        if not days.strip().isdigit():
            self._say("That is not a number of days")
            return
        today = date.today()
        entry = suppressions.Suppression(
            address=verdict.address,
            finding=verdict.tone,
            until=today + timedelta(days=int(days)),
            reason="",
        )
        try:
            written = suppressions.add(self.workspace.path, entry, on=today)
        except ValueError as refused:
            self._say(str(refused))
            return
        self._say(f"Suppressed until {entry.until.isoformat()} — recorded in {written.name}")

    def open_policy_source(self) -> None:
        """Opens the rule behind a finding, once a policy set is configured."""
        self._say("No policy set is configured, so no finding has a source to open")

    def show_state(self) -> None:
        """What the engine says is out there, read through the engine."""
        self._in_the_background(
            "Reading state…",
            lambda directory: engine_commands.state(directory),
            self._state_read,
        )

    def _state_read(self, found) -> None:
        self._say(found.summary())
        if not found.is_empty:
            self.show_output("\n".join(found.resources))

    def show_provider_docs(self) -> None:
        """Documentation for the attribute under the caret, from the local index.

        There is no network call: the schema is mirrored, which is what makes
        this work on a plane — NFR-11.
        """
        page = self._files_open.current
        if page is None or self.schema is None:
            self._say(
                "No provider schema has been indexed yet"
                if self.schema is None
                else "Open a file first"
            )
            return
        buffer = page.buffer
        offset = buffer.get_iter_at_mark(buffer.get_insert()).get_offset()
        found = hover_at(page.document.data, offset, self.schema, plan=self._plan)
        if found is None:
            self._say("Nothing documented under the caret")
            return
        self.show_output(str(found))

    def compare_with(self) -> None:
        """Compares the open file with another in the workspace."""
        page = self._files_open.current
        if page is None or self.workspace is None:
            self._say("Open a file first")
            return
        self.ask_for_a_name("Compare with", lambda other: self._compare(page, other))

    def _compare(self, page, other: str) -> None:
        target = (self.workspace.path / other).resolve()

        def run() -> None:
            if not target.is_file():
                raise workspace_files.Refused(f"{other} is not a file in this workspace")
            shown = "".join(
                difflib.unified_diff(
                    page.path.read_text(encoding="utf-8").splitlines(keepends=True),
                    target.read_text(encoding="utf-8").splitlines(keepends=True),
                    fromfile=page.path.name,
                    tofile=target.name,
                )
            )
            if not shown:
                self._say(f"{page.path.name} and {target.name} are identical")
                return
            self.show_output(shown)

        self._try(run)

    def show_activity_log(self) -> None:
        """Everything this window has run, newest last.

        It is kept in memory for the session and written nowhere: a log on disk
        would be a second place plan output lives, and plan output can hold a
        value somebody would not want kept.
        """
        if not self.activity:
            self._say("Nothing has run yet")
            return
        self.show_output("\n".join(self.activity))

    def run_convergence(self, *, asked: bool = True) -> None:
        """Stands this configuration up against the local emulator.

        A rehearsal, never a prediction. It says whether the configuration
        applies cleanly against something that behaves like the cloud — not
        whether it will behave the same way in the account, which nothing here
        can know.

        It starts a container, so it is never implicit. A save can ask for it
        and then a missing runtime says nothing: the same sentence on every
        save is a banner nobody reads by the third one, and the rail already
        carries it permanently.
        """
        if self._converging:
            return
        if not self._container_runtime:
            if asked:
                self._still_true(
                    "A rehearsal needs Docker or Podman, and none was found. "
                    "Nothing has been started."
                )
            return
        if self.workspace is None or self.speculator is None:
            return

        directory = self.speculator.directory
        plan = self._plan
        schema = self.schema
        self._converging = True
        self._say("Standing it up against the emulator…")

        def finished(result) -> None:
            self._converging = False
            self._convergence = result
            self._convergence_run = result.outcome is not sandbox_convergence.Outcome.UNAVAILABLE
            self.update_status(coverage=int(result.coverage.percentage))
            self._refresh_sections()
            self.show_output(result.output or result.reason)
            self._say(result.reason)

        def work() -> None:
            scratch = Path(tempfile.mkdtemp(prefix="backsight-rehearsal-"))
            try:
                box = ministack.Sandbox()
                box.start()
                result = sandbox_convergence.converge(
                    directory,
                    box,
                    services=override.services_from_schema(schema) if schema else [],
                    scratch=scratch,
                    plan=plan,
                )
            except (ministack.SandboxError, OSError) as refused:
                result = sandbox_convergence.Result(
                    outcome=sandbox_convergence.Outcome.UNAVAILABLE,
                    coverage=sandbox_convergence.Coverage(attempted=0, converged=0),
                    reason=str(refused),
                )
            finally:
                shutil.rmtree(scratch, ignore_errors=True)
            on_main_loop(finished)(result)

        threading.Thread(target=work, name="backsight-rehearsal", daemon=True).start()

    def insert_snippet(self, name: str) -> None:
        """Inserts a block at the caret, indented to where it lands."""
        body = snippet_library.body_of(name)
        page = self._files_open.current
        if body is None or page is None:
            self._say("Open a file first")
            return
        self._insert_indented(page, body)

    def paste_from_history(self) -> None:
        """Offers what has been copied lately, rather than only the last thing."""
        items = self.clipboard_history.items
        if not items:
            self._say("Nothing has been copied yet")
            return
        listing = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        listing.add_css_class("tf-tree")
        for text in items:
            # One line each: a clipboard entry can be a whole file, and a
            # dialog that grows to hold one is not a chooser.
            label = Gtk.Label(label=_one_line(text), xalign=0.0, ellipsize=Pango.EllipsizeMode.END)
            listing.append(Gtk.ListBoxRow(child=label))
        listing.select_row(listing.get_row_at_index(0))

        dialog = Adw.MessageDialog(transient_for=self, heading="Paste from history")
        dialog.set_extra_child(listing)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("paste", "Paste")
        dialog.set_default_response("paste")
        dialog.set_close_response("cancel")

        def answered(_dialog, response: str) -> None:
            row = listing.get_selected_row()
            if response != "paste" or row is None:
                return
            page = self._files_open.current
            if page is not None:
                self._insert_indented(page, items[row.get_index()])

        dialog.connect("response", answered)
        dialog.present()

    def find_in_folder(self) -> None:
        """Searches every file in the workspace, not only the open one."""
        self.ask_for_a_name("Find in workspace", self._find_text_everywhere)

    def _find_text_everywhere(self, term: str) -> None:
        if self.workspace is None:
            return
        root = self.workspace.path
        self._say(f"Searching for {term}…")

        def work() -> None:
            hits = workspace_search.text_in(root, term)
            on_main_loop(lambda: self._show_hits(hits, term))()

        threading.Thread(target=work, name="backsight-search", daemon=True).start()

    def _show_hits(self, hits, term: str) -> None:
        if not hits:
            self._say(f"Nothing in this workspace contains {term}")
            return
        root = self.workspace.path if self.workspace else Path()
        self.show_output(
            "\n".join(
                f"{_relative_to(hit.path, root).as_posix()}:{hit.line}  {hit.text.strip()}"
                for hit in hits
            )
        )
        self._say(f"{len(hits)} line{'' if len(hits) == 1 else 's'} contain {term}")

    def find_files_named(self) -> None:
        self.ask_for_a_name("Find files named", self._find_files_named)

    def _find_files_named(self, term: str) -> None:
        if self.workspace is None:
            return
        found = workspace_search.files_named(self.workspace.path, term)
        if not found:
            self._say(f"No file here is named like {term}")
            return
        if len(found) == 1:
            self.open_file(found[0])
            return
        # More than one: the palette already knows how to choose between files,
        # and a second chooser would be a second thing to learn.
        self.show_palette("")
        self._say(f"{len(found)} files match {term}")

    def move_current(self) -> None:
        """Moves the open file into another directory in the workspace."""
        page = self._files_open.current
        if page is None or self.workspace is None:
            self._say("Open a file first")
            return
        self.ask_for_a_name("Move to folder", lambda where: self._move_to(page, where))

    def _move_to(self, page, where: str) -> None:
        directory = (self.workspace.path / where).resolve()

        def run() -> None:
            if self.workspace.path.resolve() not in directory.parents and (
                directory != self.workspace.path.resolve()
            ):
                # Moving a file out of the workspace loses it from every view
                # here, silently. Refusing is the honest answer.
                raise workspace_files.Refused(f"{where} is outside this workspace")
            after = workspace_files.move(page.path, directory)
            self._files_open.close_current()
            self.open_file(after)
            self._say(f"Moved to {where}")

        self._try(run)

    def count_to_for_each(self) -> None:
        """Converts a counted resource to keys, once the keys are known.

        The keys have to come from somewhere, and guessing them is how one
        instance quietly becomes a destroy. So this reports what it needs
        rather than inventing it.
        """
        found = self._here()
        if found is None:
            self._say("Open a file first")
            return
        _page, source, line = found
        block = navigation.enclosing(source, line)
        if block is None or block.type not in ("resource", "data"):
            self._say("Put the caret in a resource or data block")
            return
        self._still_true(
            f"Converting {block.address} to for_each needs the key each instance becomes. "
            "Nothing here can know them, and guessing turns an instance into a destroy."
        )

    def show_diff(self) -> None:
        """Shows what changed in the open file against HEAD."""
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        self._in_git(page.path, git_history.diff, self._show_git_text, "No changes against HEAD")

    def show_file_history(self) -> None:
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        self._in_git(
            page.path,
            lambda path: "\n".join(str(commit) for commit in git_history.history(path)),
            self._show_git_text,
            "Git knows nothing about this file",
        )

    def show_blame(self) -> None:
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return

        def read(path):
            return "\n".join(
                f"{line.number:>5}  {line.short}  {line.author}" for line in git_history.blame(path)
            )

        self._in_git(page.path, read, self._show_git_text, "Git knows nothing about this file")

    def discard_changes(self) -> None:
        """Puts the working change aside. It is recoverable, not gone."""
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"Discard changes to {page.path.name}?",
            body="They are stashed rather than thrown away, so `git stash pop` brings them back.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("discard", "Discard")
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect(
            "response",
            lambda _d, response: self._discard(page) if response == "discard" else None,
        )
        dialog.present()

    def _discard(self, page) -> None:
        def work() -> None:
            stashed = git_history.discard(page.path)
            on_main_loop(self._discarded)(stashed, page.path)

        threading.Thread(target=work, name="backsight-git", daemon=True).start()

    def _discarded(self, stashed, path: Path) -> None:
        self._say(str(stashed))
        if stashed.recoverable:
            self.open_file(path)
            self.refresh_vcs()

    def _in_git(self, path: Path, read, then, when_empty: str) -> None:
        """Runs a git read off the main loop and shows whatever came back."""
        self._say("Asking git…")

        def work() -> None:
            found = read(path)
            on_main_loop(lambda: then(found, when_empty))()

        threading.Thread(target=work, name="backsight-git", daemon=True).start()

    def _show_git_text(self, text: str, when_empty: str) -> None:
        if not text.strip():
            self._say(when_empty)
            return
        self.show_output(text)

    def open_in_new_tab(self) -> None:
        """Keeps the file in front, so the next thing opened does not replace it.

        The deliberate choice. Opening reuses one tab; this is how you say you
        want to keep two. It used to answer "every file opens in its own tab
        already", which was true of the behaviour and was the behaviour being
        complained about.
        """
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        self._files_open.promote(page.path)
        self._say(f"{Path(page.path).name} will stay open")

    def reopen_tab(self) -> None:
        """For good. Somebody asking for a tab back is not browsing."""
        path = self._files_open.reopen_last_closed()
        if path is None:
            self._say("Nothing has been closed")
            return
        self.open_file(path, preview=False)

    def paste_and_indent(self) -> None:
        """Pastes a block at the caret's own indentation, keeping its shape.

        Reading the clipboard is asynchronous, so the insert happens in the
        callback. A plain paste-then-fix would be two undo steps and would
        flash the wrong indentation in between.
        """
        page = self._files_open.current
        if page is None:
            return

        def pasted(clipboard, result) -> None:
            try:
                text = clipboard.read_text_finish(result)
            except GLib.Error as refused:
                self._say(f"Nothing to paste: {refused.message}")
                return
            if not text:
                self._say("The clipboard is empty")
                return
            self._insert_indented(page, text)

        self.get_clipboard().read_text_async(None, pasted)

    def _insert_indented(self, page, text: str) -> None:
        buffer = page.buffer
        at = buffer.get_iter_at_mark(buffer.get_insert())
        _found, start = buffer.get_iter_at_line(at.get_line())
        here = buffer.get_text(start, at, True)
        indent = text_lines.indentation_of(here) if not here.strip() else ""
        buffer.begin_user_action()
        buffer.delete_selection(True, True)
        buffer.insert_at_cursor(text_lines.reindent(text, indent))
        buffer.end_user_action()

    def rename_resource(self) -> None:
        """Renames the resource under the caret, everywhere, with a moved block.

        The rename is proposed and then **verified against a real plan** before
        it is applied. A rename that would destroy and recreate is refused
        rather than shown as a diff for somebody to approve at speed.
        """
        found = self._here()
        if found is None or self.workspace is None or self.speculator is None:
            self._say("Open a file in a module first")
            return
        _page, source, line = found
        block = navigation.enclosing(source, line)
        if block is None or block.type not in refactor_rename.ADDRESSABLE:
            self._say("Put the caret in a resource or data block")
            return
        self.ask_for_a_name("Rename resource", lambda name: self._rename_resource_to(block, name))

    def _rename_resource_to(self, block, name: str) -> None:
        directory = self.speculator.directory
        try:
            rename = refactor_rename.Rename(
                resource_type=block.labels[0],
                old_name=block.labels[1],
                new_name=name,
                kind=block.type,
            )
        except ValueError as refused:
            self._say(str(refused))
            return

        files = {
            path.relative_to(directory): path.read_bytes()
            for path in sorted(directory.glob("*.tf"))
        }
        edits = refactor_rename.edits_for(files, rename)
        if not edits:
            self._say(f"Nothing declares {rename.old_address} in this module")
            return
        proposal = refactor_gate.Proposal(
            description=f"Rename {rename.old_address} to {rename.new_address}",
            edits=edits,
            appended={Path("main.tf"): refactor_rename.moved_block(rename)},
        )
        self._say(f"Verifying {proposal.description}…")

        def work() -> None:
            with tempfile.TemporaryDirectory(prefix="backsight-refactor-") as scratch:
                verdict = refactor_gate.apply_refactor(proposal, directory, scratch=Path(scratch))
            on_main_loop(self._refactored)(verdict, proposal)

        threading.Thread(target=work, name="backsight-refactor", daemon=True).start()

    def _refactored(self, verdict, proposal) -> None:
        if verdict.refused:
            # A refusal is the gate working, so it says so where it will be read
            # rather than in a toast that has gone by the time anyone looks.
            self._still_true(f"{proposal.description} was refused — {verdict.reason}")
            return
        self.dismiss_banner()
        self._say(f"{proposal.description}. The moved block is in main.tf.")
        page = self._files_open.current
        if page is not None:
            self.open_file(page.path)

    def extract_to_module(self) -> None:
        """Moves the resource under the caret into a module of its own.

        Verified like every other refactor: proposed, planned, and refused if
        the plan destroys anything. A resource that moves into a module gets a
        new address, so without a `moved` block for it the plan is a destroy
        and a create — which for anything holding data is the worst outcome in
        the tool.
        """
        found = self._here()
        if found is None or self.workspace is None or self.speculator is None:
            self._say("Open a file in a module first")
            return
        page, source, line = found
        block = navigation.enclosing(source, line)
        if block is None or not block.address:
            self._say("Put the caret in a resource or data block")
            return
        self.ask_for_a_name(
            "Extract to module",
            lambda name: self._extract_into(page, block.address, name),
        )

    def _extract_into(self, page, address: str, module: str) -> None:
        if not refactor_extract.is_a_name(module):
            self._say("A module name is a Terraform identifier — letters, digits and underscores")
            return
        directory = self.speculator.directory
        extraction = refactor_extract.extract(
            Path(page.path),
            page.text(),
            (address,),
            module=module,
            relative_to=directory,
        )
        if extraction is None:
            self._say(f"{address} is not declared in this file")
            return
        proposal = refactor_extract.proposal_for(extraction)
        self._say(f"Verifying {proposal.description}…")

        def work() -> None:
            with tempfile.TemporaryDirectory(prefix="backsight-extract-") as scratch:
                verdict = refactor_gate.apply_refactor(proposal, directory, scratch=Path(scratch))
            on_main_loop(self._refactored)(verdict, proposal)

        threading.Thread(target=work, name="backsight-extract", daemon=True).start()

    def analyse_exposure(self) -> None:
        """Runs the exposure analysis against the plan already in hand."""
        if self._plan_document is None:
            self._say("Needs a plan first")
            return
        report = exposure.analyse(project(self._plan_document))
        self.exposure_panel.show(report)
        self.open_drawer(EXPOSURE)

    def go_to_matching_bracket(self) -> None:
        """Jumps between a block's braces, through the syntax tree."""
        found = self._here()
        if found is None:
            return
        page, source, line = found
        block = navigation.enclosing(source, line)
        if block is None:
            self._say("The caret is not inside a block")
            return
        page.go_to_line(block.last if line != block.last else block.first)

    def select_all_occurrences(self) -> None:
        """Finds every occurrence of the selection. GTK has no multiple cursors.

        The honest thing is to say what this does instead of implying an
        editing mode the toolkit cannot provide — see finding 002.
        """
        page = self._files_open.current
        if page is None:
            return
        bounds = page.buffer.get_selection_bounds()
        if not bounds:
            self._say("Select something first")
            return
        selected = page.buffer.get_text(bounds[0], bounds[1], True)
        self.show_find()
        self._find.term.set_text(selected)
        self._say("Multiple cursors are not available in this toolkit — showing every match")

    def _show_in_the_desktop(self, directory: Path) -> None:
        """Hands a directory to the desktop, and says so when it will not take it.

        `Gtk.UriLauncher` crashes outright with no display, so this uses the
        plain launch, which refuses with an error instead. A machine with no
        file manager is not a reason for the application to die.
        """
        try:
            Gio.AppInfo.launch_default_for_uri(directory.as_uri(), None)
        except GLib.Error as refused:
            self._say(f"{directory} — the desktop would not open it: {refused.message}")

    def open_terminal_here(self) -> None:
        """Opens the desktop's terminal in the open file's directory."""
        where = self._where_to_put_things()
        launcher = Gio.AppInfo.get_default_for_type("inode/directory", True)
        if launcher is None:
            self._say("This desktop offers no default handler for a directory")
            return
        self._try(lambda: launcher.launch([Gio.File.new_for_path(str(where))], None))

    def move_to_new_window(self) -> None:
        """Takes the open file to a window of its own.

        An unsaved edit stays here: moving would either lose it or carry a
        buffer between windows, and neither is what somebody dragging a tab out
        expects to happen to work they have not saved.
        """
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        if page.modified:
            self._say(f"Save {page.path.name} first — an unsaved edit does not move")
            return
        application = self.get_application()
        if application is None:
            self._say("No application to open a window from")
            return
        another = Window(application=application)
        if self.workspace is not None:
            another.open_workspace(self.workspace.path)
        another.open_file(page.path)
        another.present()
        self._files_open.close_current()

    def open_a_new_window(self) -> None:
        """An empty window, for a second workspace."""
        application = self.get_application()
        if application is None:
            self._say("No application to open a window from")
            return
        Window(application=application).present()

    def revert_current(self) -> None:
        """Puts the open file back to what is on disk, after saying what it costs.

        Destructive and named as such: the buffer is what somebody typed, and
        the only way back from this is a file they have not saved.
        """
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        if not page.modified:
            self._say(f"{page.path.name} already matches what is on disk")
            return
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"Discard the changes to {page.path.name}?",
            body="The file goes back to what is on disk. This cannot be undone.",
        )
        dialog.add_response("cancel", "Keep editing")
        dialog.add_response("revert", "Discard the changes")
        dialog.set_response_appearance("revert", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect(
            "response",
            lambda _d, answer: page.reload_from_disk() if answer == "revert" else None,
        )
        dialog.present()

    def cancel_the_run(self) -> None:
        """Stops a plan that is in flight, and says so rather than going quiet."""
        if self.speculator is None or not self._planning:
            self._say("Nothing is running")
            return
        self.speculator.cancel()
        self._planning = False
        self.update_status(planning="")
        self._say("Stopped")

    def go_to_the_first_problem(self) -> None:
        """Lands on the line of the first thing stopping this plan."""
        if not self._last_errors:
            self._say("Nothing is blocking this plan")
            return
        first = self._last_errors[0]
        where = getattr(first, "path", "") or ""
        line = int(getattr(first, "line", 0) or 0)
        if where and line:
            self.open_at(str(where), line)
            return
        self.open_drawer("Changes")

    # --- navigation history ---------------------------------------------------

    def _remember_where_we_were(self) -> None:
        """Records the caret before something moves it, for Back.

        Only a jump is recorded — going to a resource, a finding, a search hit
        — never a keystroke. A history that fills up with cursor movement is one
        where Back does nothing you can feel.
        """
        page = self._files_open.current
        if page is None:
            return
        line = page.buffer.get_iter_at_mark(page.buffer.get_insert()).get_line() + 1
        here = (page.path, line)
        if self._went_back and self._went_back[-1] == here:
            return
        self._went_back.append(here)
        del self._went_back[:-HISTORY]
        self._went_forward.clear()

    def go_back(self) -> None:
        """The last place you jumped from."""
        if not self._went_back:
            self._say("Nowhere to go back to")
            return
        page = self._files_open.current
        if page is not None:
            line = page.buffer.get_iter_at_mark(page.buffer.get_insert()).get_line() + 1
            self._went_forward.append((page.path, line))
        self._go_to_remembered(self._went_back.pop())

    def go_forward(self) -> None:
        """Undoes a Back, and nothing else."""
        if not self._went_forward:
            self._say("Nowhere to go forward to")
            return
        page = self._files_open.current
        if page is not None:
            line = page.buffer.get_iter_at_mark(page.buffer.get_insert()).get_line() + 1
            self._went_back.append((page.path, line))
        self._go_to_remembered(self._went_forward.pop())

    def _go_to_remembered(self, where: tuple[Path, int]) -> None:
        path, line = where
        if not path.exists():
            self._say(f"{path.name} is gone")
            return
        self.open_file(path, preview=False)
        page = self._files_open.current
        if page is not None:
            page.go_to_line(line)

    def switch_file(self) -> None:
        """The next open file, the way every editor's Ctrl+Tab does."""
        self._files_open.next_tab()

    def select_next_occurrence(self) -> None:
        """Selects the next place the selected word appears.

        **This is the key people press out of VS Code muscle memory expecting a
        second cursor**, and GtkSourceView 5 has no API for one. So it does the
        useful half — moves the selection to the next occurrence — and says
        once, quietly and dismissibly, what it cannot do and what to use
        instead. A dead key that answers is worth more than a dead key.
        """
        page = self._files_open.current
        if page is None:
            return
        if not page.select_next_occurrence():
            self._say("No other occurrence of that")
            return
        if not self._said_about_cursors:
            self._said_about_cursors = True
            self._still_true(
                "Multiple cursors are not available — GtkSourceView 5 has no API "
                "for them. Select all occurrences and Rename resource do most of "
                "what they are reached for.",
                action="What else is missing",
                then=self.show_what_it_will_not_do,
            )

    def switch_branch(self) -> None:
        """Checks out a branch by name, asking for it first."""
        self.ask_for_a_name("Switch to which branch?", self._branch_to)

    # --- presets ---------------------------------------------------------------

    def use_layout(self, name: str) -> None:
        """One of three presets, and a preset is not a mode.

        Nothing records that a preset is in force, so touching a single panel
        afterwards simply leaves it behind — there is no state to get stuck in
        and nothing to escape from.
        """
        wanted = PRESETS.get(name)
        if wanted is None:
            return
        for panel, shown in wanted.items():
            self.set_panel_shown(panel, shown)
        if name == "review":
            self.open_drawer("Changes")

    def show_font_settings(self) -> None:
        """Preferences, on the page where the editor font is chosen."""
        self.show_settings()

    def show_what_it_will_not_do(self) -> None:
        """The page almost no product writes, and this one already had the reasons.

        Three toolkit limits, the refusals that are deliberate, and what is
        simply not built yet — said plainly rather than discovered by pressing
        a key that does nothing.
        """
        mono, as_chosen = tokens.in_use("mono")
        said = LIMITS
        if not as_chosen:
            said += (
                f"\nOne more, about this copy.\n\n  The editor is drawn in {mono}, which is "
                f"not the typeface this was\n  designed in. `sudo apt install "
                "fonts-jetbrains-mono` to see it as\n  it was drawn.\n"
            )
        self.show_output(said)

    def show_release_notes(self) -> None:
        """What changed, from the changelog that ships with the application."""
        for where in (CHANGELOG, Path.cwd() / "CHANGELOG.md"):
            try:
                self.show_output(where.read_text(encoding="utf-8"))
                return
            except OSError:
                continue
        self.show_output("No release notes are installed with this copy.")

    def show_how_to_report_a_problem(self) -> None:
        """What to send, and where — printed rather than opened.

        Opening a browser goes through the desktop portal, which means it can
        appear over whatever somebody is doing in another window. Printing the
        address costs one copy and surprises nobody.
        """
        self.show_output(REPORTING)

    def open_in_new_window(self) -> None:
        """A second window on the same workspace."""
        application = self.get_application()
        if application is None:
            self._say("No application to open a window from")
            return
        another = Window(application=application)
        if self.workspace is not None:
            another.open_workspace(self.workspace.path)
        another.present()

    def open_workspace_in_a_new_window(self) -> None:
        """Another workspace, beside this one and independent of it.

        FR-APP-04. Every window holds its own workspace, plan, credentials and
        layout, so two of them are two workspaces rather than one application
        trying to be in two places. Nothing is shared, which is what makes a
        plan in one window unable to describe the other.
        """
        application = self.get_application()
        if application is None:
            self._say("No application to open a window from")
            return
        dialog = Gtk.FileDialog(title="Open a workspace in a new window")

        def chosen(source, answer) -> None:
            try:
                folder = source.select_folder_finish(answer)
            except GLib.Error:
                return
            if folder is None or folder.get_path() is None:
                return
            another = Window(application=application)
            another.open_workspace(Path(folder.get_path()))
            another.present()

        dialog.select_folder(self, None, chosen)

    def clone_a_repository(self) -> None:
        """Fetches one and opens it. The one git operation that reaches out."""
        application = self.get_application()
        if application is None:
            return
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Clone a repository",
            body="It will be fetched into a folder you choose, and opened.",
        )
        field = Gtk.Entry(placeholder_text="https://example.invalid/team/infrastructure.git")
        field.set_margin_start(12)
        field.set_margin_end(12)
        dialog.set_extra_child(field)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("choose", "Choose a folder…")
        dialog.set_response_appearance("choose", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("choose")
        dialog.set_close_response("cancel")

        def answered(_dialog, said: str) -> None:
            url = field.get_text().strip()
            if said != "choose" or not url:
                return
            self._ask_where_to_clone(url)

        field.connect("activate", lambda *_: dialog.emit("response", "choose"))
        dialog.connect("response", answered)
        dialog.present()

    def _ask_where_to_clone(self, url: str) -> None:
        picker = Gtk.FileDialog(title="Where to put it")

        def chosen(source, answer) -> None:
            try:
                folder = source.select_folder_finish(answer)
            except GLib.Error:
                return
            if folder is None or folder.get_path() is None:
                return
            self._clone_into(url, Path(folder.get_path()) / _repository_name(url))

        picker.select_folder(self, None, chosen)

    def _clone_into(self, url: str, into: Path) -> None:
        if into.exists():
            self._still_true(f"{into.name} is already there. Nothing was fetched.")
            return
        self._say(f"Cloning into {into.name}…")

        def finished(refused: str) -> None:
            if refused:
                self._still_true(f"The clone did not finish: {refused}")
                return
            self.open_workspace(into)

        def work() -> None:
            on_main_loop(finished)(working.clone(url, into))

        threading.Thread(target=work, name="backsight-clone", daemon=True).start()

    def ask_for_a_name(self, title: str, then) -> None:
        """One dialog for anything that needs a name.

        The default is the current name, selected, so renaming is one word and
        creating is one word.
        """
        if self.workspace is None:
            self._say("Open a workspace first")
            return
        entry = Gtk.Entry(activates_default=True)
        dialog = Adw.MessageDialog(transient_for=self, heading=title, extra_child=entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("do", title.split()[0])
        dialog.set_default_response("do")
        dialog.set_close_response("cancel")

        def answered(_dialog, response: str) -> None:
            if response == "do" and entry.get_text().strip():
                then(entry.get_text().strip())

        dialog.connect("response", answered)
        dialog.present()

    def _where_to_put_things(self) -> Path:
        """The directory a new file belongs in: beside the open one."""
        page = self._files_open.current
        if page is not None:
            return page.path.parent
        return self.workspace.path if self.workspace else Path.cwd()

    def new_file(self) -> None:
        """Asks for a name and makes one, from wherever the request came from."""
        self.ask_for_a_name("New file", self._make_file)

    def _make_file(self, name: str) -> None:
        where = self._where_to_put_things() / name
        self._try(lambda: self.open_file(workspace_files.create(where)))

    def _make_folder(self, name: str) -> None:
        self._try(lambda: workspace_files.create_folder(self._where_to_put_things() / name))
        self._show_files()

    def rename_current(self) -> None:
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        self.ask_for_a_name("Rename file", lambda name: self._rename_to(page, name))

    def _rename_to(self, page, name: str) -> None:
        def run() -> None:
            after = workspace_files.rename(page.path, name)
            # The tab still holds the old path, so it is closed and the file
            # reopened rather than left pointing at somewhere nothing is.
            self._files_open.close_current()
            self.open_file(after)
            self._say(f"Renamed to {after.name}")

        self._try(run)

    def duplicate_current(self) -> None:
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        self._try(lambda: self.open_file(workspace_files.duplicate(page.path)))

    def remove_current(self) -> None:
        """Moves the open file to the trash, after asking.

        It is confirmed and it is reversible. Both, not either: a confirmation
        with no way back still relies on reading the dialog properly.
        """
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=f"Move {page.path.name} to the trash?",
            body="It goes to the desktop trash, so it can be put back.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("trash", "Move to trash")
        dialog.set_response_appearance("trash", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def answered(_dialog, response: str) -> None:
            if response != "trash":
                return
            self._try(lambda: self._trash(page))

        dialog.connect("response", answered)
        dialog.present()

    def _trash(self, page) -> None:
        removed = workspace_files.remove(page.path, to_trash=_to_the_trash)
        self._files_open.close_current()
        self._show_files()
        self._say(str(removed))

    def save_as(self) -> None:
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        self.ask_for_a_name("Save as", lambda name: self._save_as(page, name))

    def _save_as(self, page, name: str) -> None:
        def run() -> None:
            target = page.path.parent / name
            if target.exists():
                raise workspace_files.Refused(f"{name} already exists")
            Document(path=target, data=page.content()).write()
            self.open_file(target)
            self._say(f"Saved as {name}")

        self._try(run)

    def _try(self, run) -> None:
        """Runs a file operation and reports a refusal instead of raising it."""
        try:
            run()
        except (workspace_files.Refused, OSError) as refused:
            self._say(str(refused))

    def closed_the_last_file(self) -> None:
        """What the editor shows once every tab has gone."""
        self._show_the_right_nothing()

    def close_untouched(self) -> None:
        """Closes what the plan does not touch, leaving what the change is about."""
        if self._plan is None:
            self._say("Needs a plan to know what is untouched")
            return
        touched = {
            place.path
            for place in (self._source_map().places.values() if self._source_map() else ())
        }
        self._files_open.close_untouched(touched)

    def _source_map(self):
        if self.workspace is None or self.speculator is None:
            return None
        module = self.workspace.module_at(self.speculator.directory)
        return SourceMap.build(self.workspace, module) if module is not None else None

    def pin_tab(self) -> None:
        pinned = self._files_open.pin_current()
        self._say("Pinned" if pinned else "Unpinned")

    def reveal_in_rail(self) -> None:
        """Expands the open file's module in the rail and says which it is."""
        page = self._files_open.current
        if page is None or self.workspace is None:
            return
        module = self._module_for(page.path.resolve())
        if module is None:
            self._say("This file is outside every module in the workspace")
            return
        self.show_panel("left_rail")
        self._say(f"In {module.path.relative_to(self.workspace.path).as_posix() or '.'}")

    def copy_resource_addresses(self) -> None:
        """Every address declared in the open file, one per line."""
        found = self._here()
        if found is None:
            self._say("Open a file first")
            return
        _page, source, _line = found
        addresses = [block.address for block in navigation.blocks(source) if block.address]
        if not addresses:
            self._say("This file declares no addressable blocks")
            return
        self.clipboard_history.remember("\n".join(addresses))
        self.get_clipboard().set("\n".join(addresses))
        self._say(f"Copied {len(addresses)} address{'' if len(addresses) == 1 else 'es'}")

    def open_containing_folder(self) -> None:
        page = self._files_open.current
        if page is None:
            return
        self._show_in_the_desktop(page.path.parent)

    def _here(self) -> tuple[object, bytes, int] | None:
        """The open page, its bytes, and the line the caret is on."""
        page = self._files_open.current
        if page is None:
            return None
        buffer = page.buffer
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        line = buffer.get_iter_at_mark(buffer.get_insert()).get_line() + 1
        return page, text.encode("utf-8"), line

    def run_line_operation(self, name: str) -> None:
        """Runs one of the line operations on the open file."""
        page = self._files_open.current
        if page is None:
            return
        page.view.grab_focus()
        editing.run(page.buffer, name)

    def zoom(self, by: int) -> None:
        """Makes the editor text bigger, smaller, or the size it was designed.

        It says the new size out loud, because a step that hit the end and did
        nothing is otherwise indistinguishable from a shortcut that is broken.
        """
        level = self.theme.zoom
        moved = level.reset() if by == 0 else (level.bigger() if by > 0 else level.smaller())
        if moved.size == level.size and by != 0:
            self._say(f"Editor text is already at its {'largest' if by > 0 else 'smallest'}")
            return
        self.theme.set_zoom(moved)
        # The row is set in pixels from the font in use, so a new font size
        # needs it computed again — see `app/leading.py`.
        for page in self._files_open.every_page():
            keep_the_row(page.view, tokens.LINE["code"])
        self._say(
            "Editor text back to its normal size"
            if moved.is_default
            else f"Editor text at {moved.size:g}px"
        )

    def _go_to_block(self, *, start: bool) -> None:
        """Moves to the start or end of the block around the caret."""
        found = self._here()
        if found is None:
            return
        page, source, line = found
        where = navigation.start_of(source, line) if start else navigation.end_of(source, line)
        if where is None:
            self._say("No block that way")
            return
        page.go_to_line(where)

    def select_enclosing_block(self) -> None:
        """Selects the whole block the caret is in."""
        found = self._here()
        if found is None:
            return
        page, source, line = found
        block = navigation.enclosing(source, line)
        if block is None:
            self._say("The caret is not inside a block")
            return
        page.select_lines(block.first, block.last)

    def go_to_definition(self) -> None:
        """Jumps to where the address under the caret is declared.

        It looks across the workspace, not only this file: a reference is
        usually somewhere other than the declaration, which is the point.
        """
        found = self._here()
        if found is None:
            return
        page, source, line = found
        block = navigation.enclosing(source, line)
        address = self._address_under(page, block)
        if not address:
            self._say("Nothing under the caret to look up")
            return
        where = self._declaration_of(address)
        if where is None:
            self._say(f"Nothing in this workspace declares {address}")
            return
        path, at = where
        if path != page.path:
            self.open_file(path)
        self._go_to_line(at)

    def find_references(self) -> None:
        """Lists every line mentioning the address under the caret."""
        found = self._here()
        if found is None:
            return
        page, source, line = found
        block = navigation.enclosing(source, line)
        address = self._address_under(page, block)
        if not address:
            self._say("Nothing under the caret to look for")
            return
        places = self._references_to(address)
        if not places:
            self._say(f"Nothing refers to {address}")
            return
        # The find row already knows how to walk matches, and a second list of
        # places to look would be a second thing to learn.
        self.show_find()
        self._find.term.set_text(address)
        self._say(f"{len(places)} reference{'' if len(places) == 1 else 's'} to {address}")

    def _address_under(self, page, block) -> str:
        """The address the caret is on: a selection first, then its block."""
        buffer = page.buffer
        bounds = buffer.get_selection_bounds()
        if bounds:
            selected = buffer.get_text(bounds[0], bounds[1], True).strip()
            if selected:
                return selected
        return block.address if block is not None else ""

    def _each_source(self):
        """Every Terraform file in the workspace, with its bytes."""
        if self.workspace is None:
            return
        for module in self.workspace.modules:
            for path in module.files:
                try:
                    yield path, path.read_bytes()
                except OSError:
                    # A file that vanished between the walk and the read is not
                    # a reason to abandon the search.
                    continue

    def _declaration_of(self, address: str):
        for path, source in self._each_source():
            block = navigation.declaring(source, address)
            if block is not None:
                return path, block.first
        return None

    def _references_to(self, address: str) -> list[tuple[Path, int]]:
        return [
            (path, line)
            for path, source in self._each_source()
            for line in navigation.references_in(source, address)
        ]

    def convert_line_endings(self, to) -> None:
        """Rewrites the open file's line endings. One undo step, one file."""
        self._rewrite(lambda text: text_handling.convert_line_endings(text, to), to.name)

    def convert_indentation(self, *, to_tabs: bool) -> None:
        """Converts indentation, keeping whatever width the file already uses.

        Imposing a width would be a second change nobody asked for, and this
        product does not reformat.
        """

        def convert(text: str) -> str:
            found = text_handling.detect_indentation(text)
            return text_handling.convert_indentation(text, to_tabs=to_tabs, width=found.width)

        self._rewrite(convert, "tabs" if to_tabs else "spaces")

    def _rewrite(self, change, said: str) -> None:
        """Applies a whole-file change to the buffer, and says if it did nothing.

        Silence after a menu item is indistinguishable from a broken one.
        """
        page = self._files_open.current
        if page is None:
            self._say("Open a file first")
            return
        buffer = page.buffer
        before = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        after = change(before)
        if after == before:
            self._say(f"Already {said}")
            return
        page.replace_all(after)
        self._say(f"Converted to {said}")

    def show_about(self) -> None:
        """What Backsight is, which build this is, and which engine it found."""
        AboutDialog(
            version=__version__,
            commit=_build_commit(),
            engine=self._engine_version(),
            on_shortcuts=self.show_keyboard_reference,
        ).present(self)

    def _say_if_the_engine_is_missing(self) -> str:
        """Names the missing binary and how to get it, once, when it matters.

        Everything but planning works without it — reading, editing, searching,
        the file rail — so this is said when a workspace with Terraform in it is
        opened rather than at launch, and it is a banner rather than a toast
        because it stays true until somebody installs something.
        """
        if self.workspace is None or not self.workspace.is_terraform:
            return ""
        if self._engine_version():
            return ""
        binary = str(self.settings.get("terraform.binary", "tofu"))
        said = (
            f"{binary} is not on PATH, so nothing here can plan. "
            f"Install OpenTofu, or name a different binary in Preferences."
        )
        self._still_true(said)
        return said

    def _engine_version(self) -> str:
        """Which Terraform is on PATH, or nothing when there is none.

        Asked once and remembered: it cannot change while the window is open,
        and a bug report needs it more often than the window needs to be quick.
        """
        if self._engine_found is None:
            self._engine_found = _read_engine_version(self.settings.get("terraform.binary", "tofu"))
        return self._engine_found

    def open_workspace_settings(self) -> None:
        """Opens this workspace's settings file, creating it if it is absent."""
        if self.workspace is None:
            self._say("Open a workspace first")
            return
        path = self.workspace.path / ".backsight" / "settings.toml"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(WORKSPACE_SETTINGS, encoding="utf-8")
        self.open_file(path)

    def open_settings_folder(self) -> None:
        """Shows where the user's own settings live. It does not open the file.

        Two settings files exist and they are not interchangeable; naming the
        directory is more use than silently picking one.
        """
        directory = Path.home() / ".config" / "backsight"
        directory.mkdir(parents=True, exist_ok=True)
        self._show_in_the_desktop(directory)

    def show_find(self) -> None:
        """Opens the find row over the file in front, and puts the cursor in it."""
        page = self._files_open.current
        if page is None:
            self._say("Open a file to search it")
            return
        self._find.search_in(page.search)
        self._find.set_visible(True)
        self._find.term.grab_focus()

    def hide_find(self) -> None:
        self._find.set_visible(False)
        page = self._files_open.current
        if page is not None:
            page.view.grab_focus()

    def _to_the_editor(self, action: str, *arguments: object) -> None:
        """Sends an editing action to the open file's view.

        The text view owns undo, the clipboard and the selection; the menu item
        has to reach it rather than reimplement any of them.
        """
        page = self._files_open.current
        if page is None:
            return
        page.view.grab_focus()
        if "." in action:
            page.view.activate_action(action, None)
            return
        page.view.emit(action, *arguments)

    def copy_path(self, which: str) -> None:
        """Puts one form of the open file's path on the clipboard."""
        page = self._files_open.current
        if page is None:
            return
        path = page.path
        if which == "name":
            text = path.name
        elif which == "absolute":
            text = str(path)
        elif which == "repository" and self.workspace is not None:
            text = _relative_to(path, self.workspace.path).as_posix()
        elif which == "module" and self.speculator is not None:
            text = _relative_to(path, self.speculator.directory).as_posix()
        elif which == "module-source" and self.workspace is not None:
            # What another module would write to call this one.
            module = self._module_for(path.resolve())
            where = module.path if module is not None else path.parent
            text = f"./{_relative_to(where, self.workspace.path).as_posix()}".rstrip("/.")
        else:
            text = str(path)
        self.get_clipboard().set(text)
        self.clipboard_history.remember(text)
        self._say(f"Copied {text}")

    def _came_back(self, *_args) -> None:
        if self.is_active():
            self.check_files_on_disk()

    def _footer_rule_follows(self, *_args) -> None:
        self._footer_rule.set_visible(self.apply_gate.get_visible())

    def run_footer_command(self, command: str) -> None:
        """The one thing the footer offers, whatever it happens to be."""
        if command == "plan-now":
            self.plan_now()
        elif command == "cancel-plan":
            self.cancel_plan()
        elif command == "fix-and-replan":
            self.fix_everything_fixable()
        elif command == "apply":
            self.apply_plan()
        elif command == "open-changes":
            self._reviewed = True
            self.open_drawer("Changes")
            self._refresh_apply()

    def apply_plan(self) -> None:
        """Applies the plan that was reviewed, and shows it happening.

        The confirmation is the gate's; this is what happens after somebody has
        passed it. Nothing here re-plans: planning again between review and
        apply means the thing approved is not the thing that runs.
        """
        if self._applying:
            return
        if self._plan is None or self._plan_artifact is None:
            self._still_true("There is no plan to apply. Run one first.")
            return
        blocked = analysis_sections.why_apply_is_blocked(
            self._plan, self._capabilities(), len(self._plan.changes)
        )
        if blocked:
            self._still_true(blocked)
            return
        if self.workspace is None or self.speculator is None:
            return

        directory = self.speculator.directory
        plan = self._plan
        artifact = self._plan_artifact
        progress = applying.Progress(steps=applying.steps_for(plan))

        window = ApplyWindow(parent=self, on_stop=self.stop_after_this_resource)
        self._apply_window = window
        self._applying = True
        window.begin(progress, where=self._environment())
        window.present()
        began = time.monotonic()

        def moved(found: applying.Progress) -> None:
            on_main_loop(window.show)(found, elapsed=time.monotonic() - began)

        def ended(outcome) -> None:
            self._applying = False
            # Read the state back rather than trusting the exit code. "Applied"
            # is not "working", and this is the half of that anybody can check.
            checked = verifying.verify(plan, directory)
            window.finished(outcome.progress, checked)
            self._after_apply(outcome, checked)

        def work() -> None:
            outcome = applying.run(
                directory,
                artifact,
                plan=plan,
                on_step=moved,
                started=lambda run: setattr(self, "_apply_run", run),
            )
            on_main_loop(ended)(outcome)

        threading.Thread(target=work, name="backsight-apply", daemon=True).start()

    def stop_after_this_resource(self) -> None:
        """Lets the resource in flight finish and starts nothing further.

        The engine decides when it stops, so this asks and says it asked. A
        harder signal would take it mid-resource and leave the state file
        describing infrastructure that has already moved.
        """
        run = getattr(self, "_apply_run", None)
        if run is None or not self._applying:
            self._say("Nothing is being applied")
            return
        if run.stop_after_this_step():
            self._say("Stopping after this resource")
        else:
            self._say("The apply had already finished")

    def _after_apply(self, outcome, checked) -> None:
        """What the rest of the window does once an apply has stopped.

        The plan is gone either way. A plan describes a difference that no
        longer exists once it has been applied, and leaving it on screen would
        be the window making a claim about infrastructure that has moved.
        """
        self._plan = None
        self._planned_at = 0.0
        self._plan_document = None
        self._plan_artifact = None
        self._reviewed = False
        self._files_open.show_verdicts([])
        self._refresh_sections()
        self._refresh_apply()
        self._refresh_statuses()
        self.show_output(outcome.output)
        if self.speculator is not None:
            applying.keep(self.speculator.directory, outcome)
        self.record_activity(
            activity.What.APPLIED,
            detail=f"{outcome.progress.done} of {len(outcome.progress.steps)}",
            outcome="stopped part way"
            if outcome.progress.is_partial
            else ("done" if outcome.ok else "failed"),
        )
        if outcome.progress.is_partial:
            self._still_true(
                "The last apply stopped part way. Some resources changed and "
                "some were never started — check the state before planning again."
            )
        elif not outcome.ok:
            self._still_true(outcome.progress.failure or "The apply did not finish")
        else:
            self._say(checked.summary)

    def cancel_plan(self) -> None:
        """Stops a plan that is running. Nothing to say when none is."""
        if self.speculator is None or not self._planning:
            return
        self.speculator.cancel()
        self._planning = False
        self._refresh_apply()
        self._say("Plan cancelled")

    def fix_everything_fixable(self) -> None:
        """Applies every deterministic fix, then plans again.

        One pass per file, back to front, so an earlier edit cannot move the
        line a later one was measured against.
        """
        source = self._source_of(self._last_errors)
        found = [
            (error, repair.explain(error, source.get(error.path, "")).repair)
            for error in self._last_errors
        ]
        fixable = [(error, fix) for error, fix in found if fix is not None]
        if not fixable:
            self.plan_now()
            return
        for error, fix in sorted(fixable, key=lambda pair: -pair[1].line):
            self.fix_and_replan(error, fix)

    def plan_now(self) -> None:
        """Plans the open module, or says why there is nothing to plan.

        It used to call `save_current` and rely on the save to start a plan,
        which meant Run plan never ran one — it saved and hoped. Turning off
        "Plan when you save" then took the button with it, and even with the
        setting on the person waited out a debounce that exists for a burst of
        saves rather than for somebody who pressed a button.

        The save stays, because planning a module whose buffer is ahead of the
        file on disk answers a question about a file that does not exist.
        """
        if self.speculator is None:
            self._say("Open a file to plan its module")
            return
        self.save_current()
        self.speculator.now()

    def close_tab(self) -> None:
        """Closes the tab in front, and does nothing when there is none."""
        self._files_open.close_current()

    def run_tests_in_file(self) -> None:
        """Runs the tests in the open file, which is the smallest unit there is."""
        page = self._files_open.current
        if page is None or not page.path.name.endswith(".tftest.hcl"):
            self._say("Open a test file to run it")
            return
        self.run_file_tests(page.path)

    def toggle_full_screen(self) -> None:
        self.unfullscreen() if self.is_fullscreen() else self.fullscreen()

    def show_settings(self) -> None:
        SettingsDialog(
            self.settings,
            parent=self,
            keymap=self.keymap,
            on_rebind=self.rebind,
            on_change=self.settings_changed,
        ).present()

    def settings_changed(self, key: str, value: object) -> None:
        """Takes a changed setting now, rather than on the next launch.

        A preferences window whose switches need a restart is a config file
        with a nicer face.
        """
        self.settings = load_settings(self.workspace.path if self.workspace else None)
        self._files_open.settings = self.settings
        if key.startswith("editor."):
            self._files_open.reapply_display()
            self._resync_view_ticks()
        if key == "appearance.color_scheme":
            self.theme.prefer(str(value))
        if key.startswith("appearance.editor_scheme") or key == "editor.font_family":
            self.theme.read_from(self.settings)
        if key == "analysis.drift_every_minutes":
            self._start_watching_for_drift()
        if key.startswith(("tabs.", "rail.", "files.")):
            self._files_open.reapply_display()
            self._refresh_statuses()
        self._say(f"{key.rsplit('.', 1)[-1].replace('_', ' ').capitalize()} changed")

    def run_file_tests(self, path: Path) -> None:
        """Runs one test file, which is the smallest unit the engine accepts."""
        if self.workspace is None:
            return
        directory = self.workspace.path
        self.test_panel.waiting(f"Running {Path(path).name}…")

        def work() -> None:
            relative = _relative_to(Path(path), directory)
            outcome = test_run.run(directory, files=[relative])
            on_main_loop(self._tests_finished)(outcome)

        threading.Thread(target=work, name="backsight-tests", daemon=True).start()

    def _tests_finished(self, outcome) -> None:
        self.test_panel.show(outcome.results, target=outcome.target)
        if self.workspace is not None:
            self._files_open.show_test_results(outcome.results, self.workspace.path)
        self._last_results = outcome.results

    def toggle_console(self) -> None:
        """Opens the drawer at the console, or puts the drawer away."""
        if self.layout.is_shown("plan_drawer") and self._drawer.section == "Console":
            self.hide_panel("plan_drawer")
            return
        self.open_drawer("Console")
        self.console_panel.entry.grab_focus()

    def evaluate(self, expression: str) -> None:
        """Evaluates one expression against the open workspace.

        One process per expression: the engine's console exits on the first
        error and would take the rest of the session with it.
        """
        if self.speculator is None:
            self.console_panel.show(
                expression_console.Evaluation(
                    expression=expression,
                    failure=expression_console.Failure(
                        summary="No workspace is open",
                        detail="Open a directory with Terraform files in it first.",
                    ),
                )
            )
            return
        directory = self.speculator.directory

        def work() -> None:
            answer = expression_console.evaluate(directory, expression)
            on_main_loop(self.console_panel.show)(answer)

        threading.Thread(target=work, name="backsight-console", daemon=True).start()

    def run_tests(self, target: test_run.Target = test_run.DEFAULT_TARGET) -> None:
        """Runs the workspace's tests. Mocks unless told otherwise, never real
        without the confirmation an apply gets."""
        if self.workspace is None:
            self.test_panel.waiting("Open a workspace to test it")
            return
        directory = self.workspace.path
        self.test_panel.waiting(f"Running against {target.value}…")

        def finished(outcome) -> None:
            self._tests_finished(outcome)
            self.update_status(
                tests=(outcome.results.passed, outcome.results.total)
                if outcome.results.total
                else None
            )

        def work() -> None:
            outcome = test_run.run(directory, target=target)
            on_main_loop(finished)(outcome)

        threading.Thread(target=work, name="backsight-tests", daemon=True).start()

    def _remember_layout(self) -> None:
        """Writes this workspace's layout, if the person asked us to remember.

        A workspace has to be open for there to be anything to key it on, so a
        layout changed with no workspace is this session's and no longer.
        """
        if self.workspace is None or not self.settings.get("layout.remember_per_workspace"):
            return
        remembered.remember(self.workspace.path, self.layout)

    def _apply(self, name: str) -> None:
        widget = self._panels.get(name)
        if widget is not None:
            widget.set_visible(self.layout.is_shown(name))
        if name == "left_rail":
            self._settle_the_rail()
        if name == "plan_drawer":
            self._settle_the_bottom()
        if name == "menu_bar":
            # **No item is ever in two places.** The eight menus live in `☰`
            # while the bar is off, and move to the bar when it comes on —
            # rather than appearing in both, where nobody can tell which is
            # authoritative and a contributor adds to one of them.
            shown = self.layout.is_shown("menu_bar")
            self._hamburger.set_menu_model(menu_bar.everything(self.keymap, bar_shown=shown))
            # `☰` is the last surface there is and never goes: hiding a
            # browsable surface reveals the next one down, and this is the
            # bottom of that stack.
            self._hamburger.set_visible(True)


def _repository_name(url: str) -> str:
    """What a clone would be called, out of its URL.

    `.git` off the end and everything before the last slash gone. A URL nobody
    can read a name out of becomes `repository`, which is a folder somebody can
    rename rather than a crash.
    """
    said = url.strip().rstrip("/")
    said = said.rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    said = said[: -len(".git")] if said.endswith(".git") else said
    return said or "repository"


def _relative_to(path: Path, workspace: Path) -> Path:
    """The engine's `-filter` wants a path relative to where it runs."""
    try:
        return path.resolve().relative_to(Path(workspace).resolve())
    except ValueError:
        return path


def _flip(action: Gio.SimpleAction, apply) -> None:
    """Turns a layer on or off and remembers which it now is."""
    now = not action.get_state().get_boolean()
    action.set_state(GLib.Variant.new_boolean(now))
    apply(now)


def _to_the_trash(path: Path) -> None:
    """The desktop's own trash. Never a delete, and never a fallback to one."""
    Gio.File.new_for_path(str(path)).trash(None)


def _one_line(text: str) -> str:
    """A clipboard entry as one line, so a whole file does not become a dialog."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    lines = len(text.strip().splitlines())
    return first if lines <= 1 else f"{first} … ({lines} lines)"


def _irreversible_count(plan) -> int:
    """How many changes cannot be rolled back.

    A replace and a destroy are one consequence to somebody deciding, even
    though the gutter tells them apart.
    """
    if plan is None:
        return 0
    return sum(
        1
        for change in getattr(plan, "effective", ())
        if change.action.value in ("delete", "replace")
    )


def _read_engine_version(binary: str) -> str:
    """The engine's own version string, or an empty one when it is not there."""
    try:
        found = capture([binary, "version", "-json"], cwd=Path.cwd(), timeout=10.0)
    except (RunTimedOut, OSError):
        return ""
    if not found.ok:
        return ""
    try:
        return str(json.loads(found.out).get("terraform_version", ""))
    except json.JSONDecodeError:
        return ""


def _build_commit() -> str:
    """The short commit this was built from, when the tree is a repository.

    An installed build has no repository, and saying nothing is better than
    saying a commit that is not the one running.
    """
    try:
        found = capture(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[3],
            timeout=5.0,
        )
    except (RunTimedOut, OSError):
        return ""
    return found.out.strip() if found.ok else ""
