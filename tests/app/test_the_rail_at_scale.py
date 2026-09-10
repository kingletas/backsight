"""The rail against a workspace shaped like a real module library.

**Every rule in this file broke on `~/Development/terraform` and passed on the
fixtures.** Those are four to ten files in one or two modules; these are all
about twenty-something of something, so none of them could have failed.

`fixtures/library` is that shape, invented: two groups of directories, root
modules beside library modules under one folder, no backend anywhere, and
enough files that dumping the whole tree fills the rail before the top of it
has been read.
"""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.offscreen import use_a_private_display  # noqa: E402

use_a_private_display()

from backsight.app.window import Window  # noqa: E402

WHERE = Path(__file__).resolve().parents[2] / "fixtures" / "library"


@pytest.fixture
def opened():
    window = Window()
    window.open_workspace(WHERE)
    return window


def on_screen(window) -> list[str]:
    """Every row the tree is currently drawing, in order."""
    model = window._files._model
    return [model.get_row(at).get_item().entry.shown for at in range(model.get_n_items())]


def open_rows(window) -> list[str]:
    model = window._files._model
    return [
        model.get_row(at).get_item().entry.name
        for at in range(model.get_n_items())
        if model.get_row(at).get_expanded()
    ]


def test_the_fixture_is_the_shape_this_file_is_about():
    """A guard on the fixture rather than on the code: if somebody trims it,
    every test below starts passing for the wrong reason."""
    from backsight.engine.workspace.discovery import discover

    workspace = discover(WHERE)
    assert len(workspace.root_modules) >= 8, "not enough modules to fill a rail"
    assert any(not module.is_root for module in workspace.modules), "no library module"
    assert not any(module.backend for module in workspace.modules), "a backend would gate the glyph"


# --- the default state -----------------------------------------------------


def test_the_root_shows_its_immediate_children_and_nothing_else(opened):
    """**Show the repository. Let the reader choose what to open.**"""
    assert on_screen(opened) == ["examples/", "modules/", "README.md"]


def test_nothing_is_expanded_when_the_workspace_opens(opened):
    assert open_rows(opened) == []


def test_a_file_is_not_in_the_tree_because_its_directory_exists(opened):
    assert not any(row.endswith(".tf") for row in on_screen(opened))


def test_no_path_is_flattened_into_a_row(opened):
    """`examples/account-baseline/` as a peer of `modules/context/` destroys
    the hierarchy — it is a search result dump wearing a tree's clothes."""
    assert not any(row.count("/") > 1 for row in on_screen(opened))


# --- expanding -------------------------------------------------------------


def test_expanding_a_directory_reveals_one_level(opened):
    opened._files._row_for(WHERE / "examples").set_expanded(True)
    said = on_screen(opened)
    assert "account-baseline/" in said
    assert "data-pipeline/" in said
    assert not any(row.endswith(".tf") for row in said), "its children opened too"


def test_the_children_it_reveals_stay_closed(opened):
    opened._files._row_for(WHERE / "examples").set_expanded(True)
    assert open_rows(opened) == ["examples"]


def test_files_appear_when_and_only_when_their_directory_is_open(opened):
    for where in (WHERE / "examples", WHERE / "examples" / "network-hub"):
        opened._files._row_for(where).set_expanded(True)
    said = on_screen(opened)
    assert "main.tf" in said
    assert "versions.tf" in said


# --- revealing -------------------------------------------------------------


def test_opening_a_file_opens_only_its_own_ancestors(opened):
    """It must not also expand every other module, which is the difference
    between revealing a file and re-expanding the repository."""
    opened.open_file(WHERE / "examples" / "network-hub" / "main.tf", preview=False)
    assert open_rows(opened) == ["examples", "network-hub"]


def test_and_the_file_it_opened_is_the_one_marked(opened):
    wanted = WHERE / "examples" / "network-hub" / "main.tf"
    opened.open_file(wanted, preview=False)
    row, _mark = opened._files.rows[wanted.resolve()]
    assert "tf-current" in row.get_css_classes()


def test_what_was_opened_stays_open_when_the_plan_changes(opened):
    """A tree rebuilt every time a plan finishes is a tree that closes under
    you, and what somebody has opened is the only state in the rail worth
    anything."""
    opened._files._row_for(WHERE / "modules").set_expanded(True)
    opened._refresh_statuses()
    opened._show_files()
    assert open_rows(opened) == ["modules"]


# --- what it says on a row -------------------------------------------------


def test_the_rail_stays_quiet_when_a_warning_would_be_on_every_row(opened):
    """Not one module here has a backend, so a glyph meaning *state is on this
    machine* says nothing about any row relative to its neighbours."""
    assert "!" not in " ".join(on_screen(opened))


def test_local_state_is_a_fact_in_the_verdict_line_instead(opened):
    """It stops nothing, so it is not a banner and not a row of glyphs. It is a
    standing fact at the size a standing fact deserves."""
    assert "local state" in opened._status_line.texts()
    assert not opened._banner.get_revealed()


def test_the_providers_are_the_modules_own_and_are_not_repeated(opened):
    """Every root locks its own, so asking all of them printed the same
    provider twice and a line too long to fit whatever it said."""
    opened.open_file(WHERE / "examples" / "network-hub" / "main.tf", preview=False)
    opened._show_providers()
    said = str(opened._status_facts.get("provider", ""))
    assert said
    assert len(said.split(", ")) == len(set(said.split(", ")))


# --- filtering -------------------------------------------------------------


def test_filtering_reveals_what_matches_rather_than_hiding_what_does_not(opened):
    """Hiding a row means knowing about every row, which means walking the
    whole repository — the cost the tree exists to avoid."""
    opened._rail_filter.set_visible(True)
    opened._rail_filter.set_text("versions")
    assert "examples" in open_rows(opened)
    assert opened._rail_hidden.get_visible()


def test_it_says_how_many_it_found(opened):
    opened._rail_filter.set_visible(True)
    opened._rail_filter.set_text("versions")
    assert opened._rail_hidden.get_label().startswith("9 files")


def test_a_filter_that_matches_nothing_says_so(opened):
    opened._rail_filter.set_visible(True)
    opened._rail_filter.set_text("zzzzz")
    assert opened._rail_hidden.get_label() == "nothing matches"


def test_escape_puts_the_field_away_and_says_nothing(opened):
    opened._rail_filter.set_visible(True)
    opened._rail_filter.set_text("versions")
    assert opened.clear_the_rail_filter()
    assert not opened._rail_filter.get_visible()
    assert not opened._rail_hidden.get_visible()


# --- reaching it without a pointer -----------------------------------------


def test_a_row_says_out_loud_whether_it_is_a_folder_or_a_file(opened):
    """ "network" and "network.tf" sound identical, and a trailing slash is not
    read out. A screen reader has to be told which kind it is."""
    from gi.repository import Gtk

    opened._files._row_for(WHERE / "examples").set_expanded(True)
    said = []
    for at in range(opened._files._model.get_n_items()):
        entry = opened._files._model.get_row(at).get_item().entry
        said.append(entry.described)
    assert "examples, folder" in said
    assert "README.md, file" in said
    assert isinstance(opened._files._list, Gtk.ListView)


def test_the_tree_takes_the_keyboard(opened):
    """`Gtk.ListView` moves between rows and `Gtk.TreeExpander` opens and
    closes them, so this is about the tree being reachable at all."""
    assert opened._files._list.get_focusable()
    assert opened._files._list.get_model() is not None


def test_nothing_is_selected_until_somebody_selects_something(opened):
    """A tree that highlights its first row on open is claiming you are
    somewhere you are not."""
    from gi.repository import Gtk

    assert opened._files._list.get_model().get_selected() == Gtk.INVALID_LIST_POSITION
