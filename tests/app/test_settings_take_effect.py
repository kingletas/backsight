"""A switch in Preferences changes what the application does.

Twenty-one of the thirty-eight settings were read by nothing at all. These are
the ones with a route through the toolkit that can be checked without a display
server driving it: each moves a setting and asks the widget what it now does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk  # noqa: E402

from backsight.app.editor import Editor, apply_display  # noqa: E402
from backsight.app.tab_marks import title  # noqa: E402
from backsight.engine.insight.file_status import FileStatus, Impact  # noqa: E402
from backsight.engine.layout.panels import Layout, Visibility  # noqa: E402
from backsight.engine.settings.layers import DEFAULTS, Settings  # noqa: E402
from backsight.engine.vcs.git import Vcs  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "stacks" / "plain" / "infra"
FILES = [ROOT / name / "main.tf" for name in ("network", "data", "api", "edge")]


def settings(**overrides) -> Settings:
    return Settings(layers={"default": dict(DEFAULTS), "user": dict(overrides)})


def test_a_new_tab_lands_beside_the_one_you_are_on():
    editor = Editor(settings=settings())
    editor.open(FILES[0])
    editor.open(FILES[1])
    editor._tabs.set_selected_page(editor._page_for(editor.pages[FILES[0].resolve()]))
    editor.open(FILES[2])
    assert [page.path.parent.name for page, _tab in editor._each()] == ["network", "api", "data"]


def test_or_at_the_end_when_that_is_what_was_asked_for():
    editor = Editor(settings=settings(**{"tabs.new_tab_position": "end"}))
    editor.open(FILES[0])
    editor.open(FILES[1])
    editor._tabs.set_selected_page(editor._page_for(editor.pages[FILES[0].resolve()]))
    editor.open(FILES[2])
    assert [page.path.parent.name for page, _tab in editor._each()] == ["network", "data", "api"]


def test_an_edit_promotes_a_preview_tab_unless_it_is_told_not_to():
    editor = Editor(settings=settings())
    editor.open(FILES[0], preview=True)
    editor.pages[FILES[0].resolve()].buffer.insert_at_cursor("# x\n")
    assert editor.preview is None


def test_promote_on_never_leaves_a_preview_a_preview():
    editor = Editor(settings=settings(**{"files.promote_preview_on": "never"}))
    editor.open(FILES[0], preview=True)
    editor.pages[FILES[0].resolve()].buffer.insert_at_cursor("# x\n")
    assert editor.preview == FILES[0].resolve()


def test_the_unsaved_mark_is_the_one_that_was_chosen():
    status = FileStatus(path=Path("main.tf"), unsaved=True)
    assert title("main.tf", status) == "main.tf •"
    assert title("main.tf", status, unsaved="asterisk") == "main.tf *"
    assert title("main.tf", status, unsaved="none") == "main.tf"


def test_a_tab_indicator_turned_off_leaves_the_slot_empty():
    editor = Editor(settings=settings(**{"tabs.indicators.vcs": "none"}))
    page = editor.open(FILES[0])
    where = FILES[0].resolve()
    editor.show_statuses({where: FileStatus(path=where, vcs=Vcs.MODIFIED)})
    assert editor._page_for(page).get_icon() is None


def test_and_left_alone_it_is_drawn():
    editor = Editor(settings=settings())
    page = editor.open(FILES[0])
    where = FILES[0].resolve()
    editor.show_statuses({where: FileStatus(path=where, vcs=Vcs.MODIFIED)})
    assert editor._page_for(page).get_icon() is not None


def test_the_plan_indicator_can_be_turned_off_on_its_own():
    editor = Editor(settings=settings(**{"tabs.indicators.plan_impact": "none"}))
    page = editor.open(FILES[0])
    editor.show_statuses(
        {FILES[0].resolve(): FileStatus(path=FILES[0].resolve(), impact=Impact.DESTROY)}
    )
    assert editor._page_for(page).get_indicator_icon() is None


def test_the_tab_width_falls_back_to_the_setting_when_there_is_nothing_to_detect(tmp_path):
    """A file with no indentation in it cannot say what its indentation is."""
    path = tmp_path / "empty.tf"
    path.write_text("# nothing indented here\n", encoding="utf-8")
    editor = Editor(settings=settings(**{"editor.tab_size": 8}))
    assert editor.open(path).indentation.width == 8


def test_completion_is_not_installed_when_it_is_turned_off():
    editor = Editor(settings=settings(**{"analysis.value_completion": False}))
    assert editor.open(FILES[0]).completion is None
    assert Editor(settings=settings()).open(FILES[1]).completion is not None


def test_the_display_settings_reach_the_view():
    editor = Editor(
        settings=settings(
            **{"editor.word_wrap": True, "editor.show_whitespace": True, "editor.rulers": True}
        )
    )
    page = editor.open(FILES[0])
    assert page.view.get_wrap_mode() is Gtk.WrapMode.WORD_CHAR
    assert page.view.get_show_right_margin()


def test_apply_display_with_no_settings_still_draws_something():
    """Every caller passed None for a year, so this path must stay safe."""
    editor = Editor()
    page = editor.open(FILES[0])
    apply_display(page.view, indentation=page.indentation)
    assert page.view.get_show_line_numbers()


def test_the_layout_opens_the_way_settings_say():
    assert Layout.opening(settings()).visibility("left_rail") is Visibility.SHOWN
    opened = Layout.opening(settings(**{"layout.left_rail": "collapsed"}))
    assert opened.visibility("left_rail") is Visibility.COLLAPSED


def test_a_layout_setting_nobody_can_parse_leaves_the_default():
    assert (
        Layout.opening(settings(**{"layout.left_rail": "sideways"})).visibility("left_rail")
        is Visibility.SHOWN
    )


def test_a_drift_check_on_every_save_does_not_say_the_same_thing_every_save():
    """The rail already carries it permanently. The same sentence on each save
    is a banner nobody reads by the third one."""
    from backsight.app.window import Window

    window = Window()
    window._container_runtime = False
    said = []
    window._still_true = said.append
    window.run_convergence(asked=False)
    assert said == []
    window.run_convergence()
    assert len(said) == 1


def test_run_plan_works_with_planning_on_save_turned_off():
    """ "Plan when you save" is about saving. Turning it off must never take
    away the button whose whole job is to plan."""
    from backsight.app.window import Window

    window = Window()
    window.settings = settings(**{"terraform.plan_on_save": False})
    window._files_open.settings = window.settings

    asked = []
    window.speculator = type(
        "Watching",
        (),
        {
            "directory": Path("."),
            "touched": lambda self: asked.append("saved"),
            "now": lambda self: asked.append("asked"),
        },
    )()
    window.plan_now()
    assert asked == ["asked"]


def test_saving_with_it_turned_off_does_not_plan():
    from backsight.app.window import Window

    window = Window()
    window.settings = settings(**{"terraform.plan_on_save": False})
    window._files_open.settings = window.settings
    asked = []
    window.speculator = type(
        "Watching",
        (),
        {
            "directory": Path("."),
            "touched": lambda self: asked.append("saved"),
            "now": lambda self: asked.append("asked"),
        },
    )()
    window.save_current()
    assert asked == []


def test_the_rail_says_what_actually_starts_a_plan_here():
    """It said "Save to plan" whatever the setting said, so with planning on
    save off it was telling somebody to do a thing that would not work."""
    from backsight.app.window import Window

    window = Window()
    on_save = window._how_a_plan_starts(Path("prod"))
    assert on_save.startswith("Save"), on_save
    assert "Run a plan" not in on_save

    window.settings = settings(**{"terraform.plan_on_save": False})
    by_hand = window._how_a_plan_starts(Path("prod"))
    assert "Run a plan" in by_hand
    assert "Save" not in by_hand

    # Both name the workspace, and both say what you get for doing it. The
    # exact words are not the point and pinning them here broke a fix to copy
    # that read "Save to plan prod", which parses as nothing.
    for said in (on_save, by_hand):
        assert "prod" in said
        assert "what would change" in said


def test_the_registry_is_never_asked_unless_somebody_turned_it_on():
    """The only thing in this application that reaches the network. An editor
    that phones a registry when it opens a workspace is announcing that
    workspace without being told to."""
    from backsight.app.window import Window
    from backsight.engine.settings.layers import DEFAULTS

    assert DEFAULTS["analysis.check_provider_versions"] is False

    window = Window()
    asked = []
    window._versions = type("V", (), {"check": lambda self, *a, **k: asked.append(a)})()
    window._providers = [("local", "2.5.1", "opentofu/local")]
    window._check_provider_versions()
    assert asked == []
