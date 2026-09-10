"""The actions the menu names actually do the thing.

Finding 007: a name in a menu with nothing behind it does nothing, silently,
and the test that checked names against a hand-written list said it was fine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.window import Window  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "fixtures" / "workspace"


@pytest.fixture
def window():
    made = Window()
    made.open_workspace(WORKSPACE)
    return made


def opened(window) -> list[Path]:
    return sorted(window._files_open.pages)


def test_the_panel_toggles_reach_the_panels_they_name():
    """Both halves worked and neither could reach the other."""
    window = Window()
    # Not `is_shown`: collapsed is not hidden, so a shown-to-collapsed toggle
    # leaves that True and the test would pass without anything happening.
    before = window.layout.visibility("left_rail")
    window.activate_action("win.toggle-left-rail", None)
    assert window.layout.visibility("left_rail") is not before


def test_closing_others_leaves_the_one_in_front(window):
    files = sorted(WORKSPACE.rglob("*.tf"))[:3]
    for path in files:
        # Deliberately, because this is about several tabs. Opening reuses.
        window.open_file(path, preview=False)
    assert len(opened(window)) == 3
    window.activate_action("win.close-others", None)
    assert len(opened(window)) == 1


def test_closing_all_leaves_nothing(window):
    for path in sorted(WORKSPACE.rglob("*.tf"))[:2]:
        window.open_file(path, preview=False)
    window.activate_action("win.close-all", None)
    assert opened(window) == []


def test_closing_saved_leaves_the_unsaved_one(window):
    """It has to leave the rest alone, or it is a data-loss button."""
    files = sorted(WORKSPACE.rglob("*.tf"))[:2]
    for path in files:
        window.open_file(path, preview=False)
    dirty = window._files_open.pages[files[0].resolve()]
    dirty.view.get_buffer().insert_at_cursor("\n# edited\n")
    window.activate_action("win.close-saved", None)
    assert opened(window) == [files[0].resolve()]


def test_copying_the_name_puts_only_the_name_on_the_clipboard(window):
    path = sorted(WORKSPACE.rglob("*.tf"))[0]
    window.open_file(path)
    said = _watch(window)
    window.copy_path("name")
    assert said and path.name in said[0]


def test_copying_the_repository_path_is_relative_to_the_workspace(window):
    path = sorted(WORKSPACE.rglob("*.tf"))[0]
    window.open_file(path)
    said = _watch(window)
    window.copy_path("repository")
    assert said and str(WORKSPACE) not in said[0]
    assert path.name in said[0]


def test_copying_with_nothing_open_says_nothing_rather_than_failing(window):
    window.copy_path("name")


def test_every_action_the_menu_wires_can_be_activated(window):
    """Activating an action that is registered but broken raises here."""
    for name in (
        "toggle-code-lens",
        "toggle-hints",
        "toggle-gutter-verdicts",
        "close-all",
        "reset-layout",
        "scheme-light",
        "scheme-follow-system",
    ):
        window.activate_action(f"win.{name}", None)


def _watch(window) -> list[str]:
    """Collects what the window says from here on."""
    said: list[str] = []
    window._say = said.append
    return said


def test_validating_a_real_workspace_reports_what_the_engine_said(window):
    """Against the real engine, in the workspace that plans offline."""
    from backsight.engine.plan import commands

    window.open_workspace(ROOT / "fixtures" / "plannable")
    answer = commands.validate(ROOT / "fixtures" / "plannable")
    said: list[str] = []
    window._say = said.append
    window._validated(answer)
    assert said and said[0] == answer.summary()


def test_a_validation_error_goes_to_the_banner_not_a_toast(window):
    """It is still true after four seconds, which is what a banner is for."""
    from backsight.engine.plan.commands import Problem, Validation

    window._validated(
        Validation(
            valid=False,
            problems=[
                Problem(
                    severity="error",
                    summary="Reference to undeclared input variable",
                    detail="Declare it.",
                    path="main.tf",
                    line=2,
                )
            ],
        )
    )
    assert window._banner.get_revealed()
    assert "main.tf:2" in window._banner.get_title()


def test_a_clean_validation_clears_a_stale_banner(window):
    from backsight.engine.plan.commands import Validation

    window._still_true("something old")
    window._validated(Validation(valid=True))
    assert not window._banner.get_revealed()


def test_formatting_never_changes_a_file(window, tmp_path):
    """Round-trip safety is a hard constraint; a menu item may not break it."""
    from backsight.engine.plan import commands

    messy = tmp_path / "main.tf"
    messy.write_text('resource "terraform_data" "a" {\n    input   =    "x"\n}\n')
    before = messy.read_bytes()
    answer = commands.formatting(tmp_path)
    assert not answer.tidy
    assert messy.read_bytes() == before


def test_an_engine_command_with_no_workspace_says_so():
    window = Window()
    said: list[str] = []
    window._say = said.append
    window.validate_workspace()
    assert said == ["Open a workspace first"]


def test_hiding_a_panel_says_nothing():
    """A view toggle is visible and reverses with the same key.

    A toast with an Undo button on it treats hiding a panel as a destructive
    act, which is how people learn to dismiss toasts without reading them —
    including the one saying an apply finished.
    """
    window = Window()
    window.show_panel("plan_drawer")
    before = len(window.activity)
    window.hide_panel("plan_drawer")
    assert len(window.activity) == before


def test_closing_the_drawer_gives_the_space_back():
    """A paned holds its position when a child is hidden, so hiding the drawer
    left the editor a grey band it could not use. Hidden has to mean gone.

    The height it settles at needs a compositor, so the smoke checks that; this
    checks the thing that was actually wrong.
    """
    window = Window()
    window.show_panel("plan_drawer")
    assert window._drawer.get_visible()
    window.hide_panel("plan_drawer")
    assert not window._drawer.get_visible()
    window.show_panel("plan_drawer")
    assert window._drawer.get_visible()


def test_nothing_else_is_left_holding_the_bottom_of_the_window_open():
    """There was a second pane under the drawer that never drew anything and
    stayed visible once anything had run, so Escape closed the drawer and left
    its band behind."""
    window = Window()
    window.show_output("tofu: something happened")
    assert window._drawer.section == "Output"
    assert "something happened" in window.output_panel.text
    window.hide_panel("plan_drawer")
    assert window._centre.get_end_child() is window._drawer
    assert not window._drawer.get_visible()


def test_output_that_says_nothing_opens_nothing():
    window = Window()
    window.show_output("   \n ")
    assert not window.layout.is_shown("plan_drawer")


def test_a_snippet_inserts_hcl_that_parses(window):
    from backsight.engine.hcl.navigation import blocks

    window.open_file(sorted(WORKSPACE.rglob("*.tf"))[0])
    page = window._files_open.current
    page.buffer.set_text("")
    window.activate_action("win.snippet-variable", None)
    text = page.buffer.get_text(page.buffer.get_start_iter(), page.buffer.get_end_iter(), True)
    assert blocks(text.encode("utf-8"))


def test_copying_a_path_remembers_it_for_the_history(window):
    window.open_file(sorted(WORKSPACE.rglob("*.tf"))[0])
    window.copy_path("name")
    assert window.clipboard_history.items


def test_pasting_from_an_empty_history_says_so(window):
    said: list[str] = []
    window._say = said.append
    window.paste_from_history()
    assert said and "Nothing has been copied" in said[0]


def test_converting_count_to_for_each_refuses_to_guess_the_keys(window):
    """Guessing a key turns an instance into a destroy."""
    window.open_file(sorted(WORKSPACE.rglob("*.tf"))[0])
    window._files_open.current.go_to_line(1)
    window.activate_action("win.count-to-for-each", None)
    assert window._banner.get_revealed()
    assert "guessing" in window._banner.get_title()


def test_moving_a_file_out_of_the_workspace_is_refused(window, tmp_path):
    """It would vanish from every view here, silently."""
    window.open_file(sorted(WORKSPACE.rglob("*.tf"))[0])
    said: list[str] = []
    window._say = said.append
    window._move_to(window._files_open.current, "../elsewhere")
    assert said and "outside this workspace" in said[0]


def test_moving_an_unsaved_file_to_a_new_window_is_refused(window):
    """It would lose the edit or carry a buffer between windows."""
    path = sorted(WORKSPACE.rglob("*.tf"))[0]
    window.open_file(path)
    window._files_open.current.buffer.insert_at_cursor("\n# edited\n")
    said: list[str] = []
    window._say = said.append
    window.move_to_new_window()
    assert said and "does not move" in said[0]
    assert window._files_open.current is not None


def test_explaining_a_finding_with_none_on_the_line_says_so(window):
    window.open_file(sorted(WORKSPACE.rglob("*.tf"))[0])
    said: list[str] = []
    window._say = said.append
    window.explain_finding()
    assert said and "No finding on this line" in said[0]


def test_suppressing_needs_a_number_of_days(window):
    from backsight.engine.insight.verdicts import Verdict

    verdict = Verdict(path=Path("main.tf"), line=1, text="x", tone="destroy", address="a.b")
    said: list[str] = []
    window._say = said.append
    window._suppress(verdict, "soon")
    assert said and "not a number of days" in said[0]


def test_every_keyboard_binding_reaches_a_real_action():
    """The keymap described the bindings and nothing installed them.

    Only `win.save` was ever bound, so every other shortcut in the application
    was a line in a document.
    """
    from backsight.engine.settings.keys import Keymap

    window = Window()
    live = set(window.list_actions())
    bound = [c.action for c in Keymap.build().commands.values() if c.accelerator]
    assert bound, "nothing is bound at all"
    assert [action for action in bound if action not in live] == []


def test_apply_has_no_shortcut():
    """It is the one irreversible thing; a key makes it the easiest accident."""
    from backsight.engine.settings.keys import Keymap

    assert Keymap.build().accelerator("apply") is None


def test_the_shortcuts_the_requirements_name_are_all_bound():
    from backsight.engine.settings.keys import Keymap

    keymap = Keymap.build()
    for action, keys in (
        ("find", "<Control>f"),
        ("replace", "<Control>h"),
        ("find-in-folder", "<Control><Shift>f"),
        ("goto-line", "<Control>l"),
        ("toggle-line-comment", "<Control>slash"),
        ("undo", "<Control>z"),
        ("zoom-in", "<Control>equal"),
        ("zoom-out", "<Control>minus"),
        ("zoom-reset", "<Control>0"),
    ):
        assert keymap.accelerator(action) == keys, action


def test_zooming_says_what_it_did(window):
    said: list[str] = []
    window._say = said.append
    window.zoom(1)
    assert said and "px" in said[0]
    window.zoom(0)
    assert "normal size" in said[-1]


def test_the_session_is_written_and_read_back(tmp_path, monkeypatch):
    """Reopening the app returns you to the files you had open."""
    from backsight.engine.layout import session

    monkeypatch.setattr(session, "directory", lambda home=None: tmp_path)
    window = Window()
    window.open_workspace(WORKSPACE)
    first = sorted(WORKSPACE.rglob("*.tf"))[0]
    window.open_file(first)
    window.remember_session()

    another = Window()
    another.open_workspace(WORKSPACE)
    assert first.resolve() in another._files_open.pages


def test_a_file_that_has_since_gone_is_skipped_in_silence(tmp_path, monkeypatch):
    """Being told about four deleted files every morning is a worse start."""
    from backsight.engine.layout import session

    monkeypatch.setattr(session, "directory", lambda home=None: tmp_path)
    session.remember_session(
        WORKSPACE, session.Session(files=[session.OpenFile("gone.tf")]), home=tmp_path
    )
    window = Window()
    said = list(window.activity)
    window.open_workspace(WORKSPACE)
    assert not window._files_open.pages
    assert "gone.tf" not in " ".join(window.activity[len(said) :])


def test_closing_saves_even_when_one_part_of_it_fails(tmp_path, monkeypatch, capsys):
    """A shutdown somebody has to kill is worse than a lost layout."""
    from backsight.engine.layout import session

    monkeypatch.setattr(session, "directory", lambda home=None: tmp_path)
    window = Window()
    window.open_workspace(WORKSPACE)

    def refuse():
        raise OSError("no room")

    window.remember_geometry = refuse
    window.closing()
    assert "could not save" in capsys.readouterr().err


def test_with_no_engine_installed_it_says_what_is_missing():
    """Everything but planning works without one, so it is said on opening a
    workspace rather than at launch — and it stays true until somebody acts."""
    window = Window()
    window.settings = type(
        "Fixed",
        (),
        {
            "get": staticmethod(
                lambda key, default=None: (
                    "not-installed-anywhere" if key == "terraform.binary" else default
                )
            )
        },
    )()
    window._engine_found = None
    window.open_workspace(WORKSPACE)
    assert "not-installed-anywhere" in window._banner.get_title()
    assert "Preferences" in window._banner.get_title()
    assert window._banner.get_revealed()


def test_and_says_nothing_when_the_engine_is_there():
    window = Window()
    window._engine_found = "1.12.6"
    window.open_workspace(WORKSPACE)
    assert window._say_if_the_engine_is_missing() == ""
