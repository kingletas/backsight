"""One test per defect that actually happened, so none of them comes back.

Every one of these shipped with a green suite. That is the point of the file:
they are not hypothetical failures, they are the ones this codebase produced,
and each is named for what somebody would have seen rather than for the code
that was wrong.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src" / "backsight"


def _source(*parts: str) -> str:
    return (SOURCE.joinpath(*parts)).read_text(encoding="utf-8")


# --- things that existed and could not be reached ---------------------------


def test_no_setting_is_offered_that_nothing_reads():
    """Twenty-one of thirty-eight were read by nothing: the dialog wrote them
    to a file and no line of code ever asked for the value."""
    from backsight.app.settings_dialog import GROUPS
    from tests.architecture.test_every_setting_is_read import _strings_in_the_code

    offered = [key for _t, _i, _d, keys in GROUPS for key in keys]
    read = _strings_in_the_code()
    assert [key for key in offered if key not in read] == []


def test_every_menu_item_reaches_something_or_says_why_not():
    """Eleven reached nothing, silently."""
    from tests.architecture.test_menus import NOT_WIRED

    assert NOT_WIRED == set()


def test_the_keymap_binds_the_keys_a_hand_reaches_for():
    """The workspace switcher printed Ctrl+O and nothing carried it, so the
    first shortcut anybody tries did nothing while the window told them to
    press it."""
    from backsight.engine.settings.keys import Keymap

    keymap = Keymap.build()
    for action in ("open-workspace", "save", "find", "full-screen", "library"):
        command = keymap.commands.get(action)
        assert command is not None and command.accelerator, action


def test_output_handed_to_the_window_is_actually_shown():
    """`show_output` revealed an empty box and threw the text away. Twelve
    callers fed it and none of it was ever drawn."""
    tree = ast.parse(_source("app", "window.py"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "show_output":
            said = ast.dump(node)
            assert "output_panel" in said
            return
    pytest.fail("show_output is gone")


def test_the_close_dialog_is_reached_from_somewhere():
    """It was written, tested, and called from nowhere — so its heading had
    never been read aloud, and it said "Close 1 tab all?"."""
    assert "close_dialog" in _source("app", "editor.py")


def test_the_completion_provider_is_installed_on_a_page():
    """It existed under a latency budget and nothing in the editor called it."""
    assert "completion.install" in _source("app", "editor.py")


def test_the_rehearsal_is_wired_to_the_sandbox():
    """It said "not wired to the sandbox yet" while the container lifecycle,
    the override and the coverage matrix all existed and were tested."""
    said = _source("app", "window.py")
    assert "sandbox_convergence.converge" in said
    assert "not wired to the sandbox yet" not in said


# --- things that were hardcoded rather than looked at -----------------------


def test_capabilities_are_read_rather_than_assumed_false():
    """`credentials` and `container_runtime` were both hardcoded False, so the
    rail said things were unavailable on a machine that had them."""
    said = _source("app", "window.py")
    assert "credentials=self._credentials.any" in said
    assert "runtime.detect() is not None" in said
    assert "policy_set=False" not in said
    assert "pricing_data=False" not in said


def test_the_status_bar_does_not_hardcode_why_apply_is_blocked():
    """It carried "credentials needed to apply" while the footer worked the
    answer out, so a plan that could be applied said both at once."""
    assert 'blocked="credentials needed to apply"' not in _source("app", "window.py")


# --- things that were said in the wrong place -------------------------------


def test_no_toast_is_asked_to_last_forever():
    """Five were. A toast that never leaves is a banner wearing a toast's
    clothes."""
    forever = []
    for path in (SOURCE / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "timeout" and isinstance(keyword.value, ast.Constant):
                    if keyword.value.value == 0:
                        forever.append(f"{path.name}:{node.lineno}")
    assert forever == []


def test_no_font_size_is_a_pixel_count():
    """px is deaf to the desktop's text scaling, so somebody at 150% saw no
    change anywhere — including the eleven-pixel status bar."""
    sheet = (SOURCE / "app" / "theme" / "components.css").read_text(encoding="utf-8")
    import re

    sizes = re.findall(r"font-size:\s*([^;]+);", sheet)
    assert [one for one in sizes if one.strip().endswith(("px", "pt"))] == []


def test_no_machine_word_is_handed_to_something_that_shows_it():
    """Preferences showed `single_click` and `default: on · user: off ← in
    effect`, which is our storage model printed into somebody's window."""
    from tests.architecture.test_no_machine_words_on_screen import _across_the_application

    assert _across_the_application() == []


# --- things that ran when they should not, or did not when they should ------


def test_run_plan_asks_for_a_plan_rather_than_saving_and_hoping():
    """It called `save_current` and relied on the save to start one, so turning
    off "plan when you save" took the button with it."""
    said = _source("app", "window.py")
    start = said.index("def plan_now")
    assert "self.speculator.now()" in said[start : start + 1200]


def test_cancelling_a_plan_reaches_the_process():
    """It bumped a generation counter and discarded the answer while `tofu`
    kept running, holding the state lock."""
    said = _source("engine", "plan", "speculation.py")
    assert "running.cancel()" in said
    assert "started=remember" in said


def test_the_registry_is_only_reached_when_somebody_asks():
    """The only thing here that touches the network."""
    from backsight.engine.settings.layers import DEFAULTS

    assert DEFAULTS["analysis.check_provider_versions"] is False
    assert DEFAULTS["docs.mirror_providers"] is False
    assert DEFAULTS["analysis.drift_every_minutes"] == 0


def test_a_second_application_is_never_built_in_one_process():
    """Two share GTK's global accel map, and the suite segfaulted under random
    ordering because of it."""
    made = []
    for path in (ROOT / "tests").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "Application()" in text and "get_default() or Application()" not in text:
            made.append(path.name)
    assert made == []


# --- things that reported success they had not earned -----------------------


def test_the_smoke_runs_every_check():
    """It had a `return 1` halfway through `main`, so it stopped on the first
    failure and reported the seventeen checks after it as clean by never
    running them."""
    said = (ROOT / "scripts" / "gui-smoke.py").read_text(encoding="utf-8")
    start = said.index("def main(")
    end = said.index("\ndef ", start + 10)
    body = said[start:end]
    # One `return 1`, and it is the last thing the function does.
    assert body.count("return 1") == 1
    assert body.index("return 1") > body.index("if failures:")


def test_the_smoke_only_claims_success_when_there_is_some():
    """It printed "every check passed" before the failures were counted."""
    said = (ROOT / "scripts" / "gui-smoke.py").read_text(encoding="utf-8")
    # The print, not the comment above it that quotes the same words.
    at = said.index('print(f"  the window drew itself and every check passed')
    assert "if not failures:" in said[at - 120 : at]


def test_a_no_op_edit_is_never_reported_as_a_change():
    """A find-and-replace that matched nothing must not report success."""
    from backsight.engine.refactor.edits import apply_to

    assert apply_to(b"unchanged", []) == b"unchanged"


def test_no_panel_divides_a_size_the_window_does_not_have_yet():
    """Twice, in the same family. The inspector's width and then the drawer's
    height were both worked out before the window had been laid out, so each
    divided zero and left its neighbour at nothing.

    The second only appeared under random test ordering, which is the kind of
    thing that reaches somebody's machine rather than a suite.
    """
    said = _source("app", "window.py")
    for method in ("_size_drawer", "_fit_the_chips"):
        start = said.index(f"def {method}")
        body = said[start : said.index("\n    def ", start + 10)]
        assert "<= 0:" in body and "return" in body, method


def test_a_push_is_not_offered_where_there_is_no_repository():
    """The button was live on a blank window and in a folder with no `.git`.

    Pressing it asked "Push this branch?" — a branch that did not exist — warned
    that other people could pull your commits, and then handed back raw git:
    `fatal: not a git repository`. Nothing had ever looked.
    """
    from backsight.engine.vcs.working import Working

    assert not Working().can_push, "nothing has looked yet, so push is refused"
    assert not Working(unreadable="not a git repository").can_push
    assert not Working(branch="main", detached=True).can_push
    assert Working(branch="main").can_push, "a real branch can still be pushed"


def test_the_docs_panel_does_not_name_a_button_that_is_not_there():
    """The empty state said "press the button" and the panel had none until a
    page had already loaded — so the one instruction on screen led nowhere."""
    from backsight.app import docs_panel

    named = docs_panel.NOTHING_YET
    assert "the button" not in named, "name the control, or there is nothing to press"
    assert "Docs for this" in named


@pytest.mark.acceptance
def test_the_open_drawer_tab_is_one_you_can_see():
    """Nine tabs are wider than the drawer, so some are always off the edge.

    The one you are reading was among them: `Esc to close` also expanded, so it
    took half the header for twelve characters, and choosing a tab by key never
    scrolled the strip. You looked at the Library panel with `Changes` lit.
    """
    gi = pytest.importorskip("gi", reason="the toolkit is not installed")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")

    from backsight.app.offscreen import use_a_private_display
    from backsight.app.window import Window
    from tests.acceptance.looking import settle

    use_a_private_display()
    window = Window()
    window.set_default_size(1280, 820)
    window.present()
    settle(window)

    drawer = window._drawer
    for section in ("library", "git", "output", "changes"):
        window.open_drawer(section)
        settle(window)
        showing = drawer._stack.get_visible_child()
        at = next(
            index
            for index in range(drawer._stack.get_pages().get_n_items())
            if drawer._stack.get_pages().get_item(index).get_child() is showing
        )
        button = drawer._switcher.get_first_child()
        for _ in range(at):
            button = button.get_next_sibling()
        found, box = button.compute_bounds(drawer._switcher)
        along = drawer._along.get_hadjustment()
        assert found
        assert box.origin.x >= along.get_value() - 1, f"{section}: tab is off the left edge"
        assert box.origin.x + box.size.width <= along.get_value() + along.get_page_size() + 1, (
            f"{section}: tab is off the right edge"
        )
    window.close()


@pytest.mark.acceptance
def test_a_narrow_window_folds_its_panels_instead_of_clipping_them():
    """At 630px a panel's text ran off the right edge of the screen.

    The panes were told not to crush their children, which is right, so the
    window simply became narrower than its own minimum and GTK clipped. Nothing
    was folding the panels away when the room ran out.

    The width is passed in rather than resized to: an X server with no window
    manager grows a window and never shrinks it, so driving this by resizing
    tested nothing and said it passed.
    """
    gi = pytest.importorskip("gi", reason="the toolkit is not installed")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")

    from backsight.app.offscreen import use_a_private_display
    from backsight.app.window import Window
    from tests.acceptance.looking import settle

    use_a_private_display()
    window = Window()
    window.present()
    settle(window)

    def at(room: int) -> bool:
        window._fold_when_there_is_no_room(room)
        return window.layout.is_shown("left_rail")

    assert at(1400), "there is room for it"
    assert at(900), "490 is what the two of them need, so 900 fits"
    assert not at(450), "there is room for neither"
    assert at(1400), "widening gives back what was folded"

    # A panel somebody put away stays away: it was never folded, so widening
    # has nothing of theirs to undo.
    window.hide_panel("left_rail")
    at(450)
    assert not at(1400), "widening must not undo a deliberate hide"
    window.close()


def test_the_folding_is_actually_wired_to_the_window_width():
    """The decision above is only worth anything if something calls it.

    The first version of this test looked for `add_breakpoint(` in the file.
    That passed with the wiring deleted, because the method holding the call
    was still there and nothing reached it — the exact defect this whole file
    exists for, written into its own guard.
    """
    from backsight.app import window as module

    tree = ast.parse(_source("app", "window.py"))
    window = next(
        node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name == "Window"
    )
    setting_up = next(
        node
        for node in window.body
        if isinstance(node, ast.FunctionDef) and node.name == "__init__"
    )
    called = {
        node.func.attr
        for node in ast.walk(setting_up)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "_fold_at_every_width" in called, "the window is never told it got narrower"

    installs = next(
        node
        for node in window.body
        if isinstance(node, ast.FunctionDef) and node.name == "_fold_at_every_width"
    )
    assert "add_breakpoint" in {
        node.func.attr
        for node in ast.walk(installs)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }, "nothing tells the window it got narrower"

    assert module.Window.FOLD_RAIL > 0, "the rail folds at a measured width, not at nothing"


@pytest.mark.acceptance
def test_the_tab_strip_draws_no_scrollbar_over_the_tabs():
    """Scrolling the strip is right; showing a bar for it is not.

    `AUTOMATIC` lays an overlay scrollbar across the bottom of the tabs
    whenever the pointer is near them, so hovering the drawer put a grey line
    through the tab labels. `EXTERNAL` scrolls exactly the same and draws
    nothing.
    """
    gi = pytest.importorskip("gi", reason="the toolkit is not installed")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk

    from backsight.app.offscreen import use_a_private_display
    from backsight.app.window import Window
    from tests.acceptance.looking import settle

    use_a_private_display()
    window = Window()
    window.set_default_size(1280, 820)
    window.present()
    settle(window)
    window.open_drawer("output")
    settle(window)

    strip = window._drawer._along
    horizontal, _vertical = strip.get_policy()
    assert horizontal is Gtk.PolicyType.EXTERNAL, "AUTOMATIC draws a bar across the tabs"

    def every(widget, found=None):
        found = [] if found is None else found
        found.append(widget)
        child = widget.get_first_child()
        while child is not None:
            every(child, found)
            child = child.get_next_sibling()
        return found

    for bar in (w for w in every(strip) if isinstance(w, Gtk.Scrollbar)):
        assert bar.get_width() == 0 or bar.get_height() == 0, "a scrollbar is taking room"

    # And the tab you opened is one you can see — by fitting, or by the strip
    # having scrolled to it. Asserting that it scrolled asserted that the tabs
    # do not fit, which stopped being true the day the close control left the
    # row: nine tabs fit at 1280 now, and a check that reads "it scrolled"
    # would be demanding the defect back.
    along = strip.get_hadjustment()
    last = window._drawer.sections[-1]
    window.open_drawer(last)
    settle(window)
    assert along.get_page_size() >= along.get_upper() or along.get_value() > 0, (
        "the open tab is off the edge and nothing scrolled to it"
    )
    window.close()


def test_refusing_a_file_does_not_close_the_one_you_were_reading(tmp_path):
    """A file that cannot be shown without damaging it is refused — and the
    refusal took the previous file with it.

    The preview tab was closed before the new file was read, so opening a
    latin-1 `.tf` left the editor emptier than it found it. Two guarantees
    collided and the wrong one won: *opening replaces the one in front* ran
    before *a file that cannot be read opens nothing*.
    """
    import pytest  # noqa: PLC0415

    gi = pytest.importorskip("gi", reason="the toolkit is not installed")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from backsight.app.window import Window  # noqa: PLC0415

    window = Window()
    good = tmp_path / "good.tf"
    good.write_text('resource "null_resource" "a" {}\n', encoding="utf-8")
    bad = tmp_path / "bad.tf"
    bad.write_bytes(b'# caf\xe9\nresource "null_resource" "b" {}\n')

    window.open_file(good, preview=True)
    assert list(window._files_open.pages) == [good.resolve()]

    window.open_file(bad, preview=True)
    assert list(window._files_open.pages) == [good.resolve()]
