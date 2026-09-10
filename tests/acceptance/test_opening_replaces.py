"""Opening a file replaces the one in front. A new tab is a deliberate choice.

Twenty files looked at was twenty tabs to close, and it was every open rather
than only browsing — a definition followed, a palette result and a click in the
rail each left one behind.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.acceptance.looking import settle

gi = pytest.importorskip("gi", reason="the toolkit is not installed")

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "stacks" / "plain" / "infra"
FILES = sorted(ROOT.rglob("main.tf"))


def tabs(window) -> list[str]:
    return [path.parent.name for path in window._files_open.pages]


@pytest.fixture
def browsing(window):
    window.open_workspace(ROOT)
    settle(window)
    return window


def test_opening_a_second_file_replaces_the_first(browsing):
    browsing.open_file(FILES[0])
    browsing.open_file(FILES[1])
    settle(browsing, 0.3)
    assert len(tabs(browsing)) == 1


def test_and_a_third_replaces_the_second(browsing):
    for one in FILES[:3]:
        browsing.open_file(one)
    settle(browsing, 0.3)
    assert tabs(browsing) == [FILES[2].parent.name]


def test_a_file_you_have_typed_in_is_never_replaced(browsing):
    """An edit promotes it, so nobody loses work to a click."""
    browsing.open_file(FILES[0])
    browsing._files_open.current.buffer.insert_at_cursor("# typed\n")
    browsing.open_file(FILES[1])
    settle(browsing, 0.3)
    assert len(tabs(browsing)) == 2


def test_keeping_the_one_in_front_is_the_deliberate_choice(browsing):
    browsing.open_file(FILES[0])
    browsing.open_in_new_tab()
    browsing.open_file(FILES[1])
    settle(browsing, 0.3)
    assert len(tabs(browsing)) == 2


# --- the rail: one click previews, two open -------------------------------


def _clicking(browsing, **user):
    from backsight.engine.settings.layers import DEFAULTS, Settings

    browsing.settings = Settings(layers={"default": dict(DEFAULTS), "user": user})
    browsing._files_open.settings = browsing.settings
    return browsing


def test_one_click_previews_and_the_next_preview_replaces_it(browsing):
    """Looking through a repository leaves no tab per click."""
    browsing._clicked(FILES[0], 1)
    browsing._clicked(FILES[1], 1)
    settle(browsing, 0.3)
    assert tabs(browsing) == [FILES[1].parent.name]
    assert browsing._files_open.preview == FILES[1].resolve()


def test_two_clicks_open_the_file(browsing):
    browsing._clicked(FILES[0], 2)
    browsing._clicked(FILES[1], 1)
    settle(browsing, 0.3)
    assert len(tabs(browsing)) == 2
    assert browsing._files_open.preview == FILES[1].resolve()


def test_a_double_click_opens_the_file_its_first_click_previewed(browsing):
    """The two presses of one double click: preview, then open the same tab."""
    browsing._clicked(FILES[0], 1)
    browsing._clicked(FILES[0], 2)
    settle(browsing, 0.3)
    assert len(tabs(browsing)) == 1
    assert browsing._files_open.preview is None


def test_one_click_opens_where_the_setting_says_so(browsing):
    _clicking(browsing, **{"files.open_on": "single_click"})
    browsing._clicked(FILES[0], 1)
    browsing._clicked(FILES[1], 1)
    settle(browsing, 0.3)
    assert len(tabs(browsing)) == 2
    assert browsing._files_open.preview is None


def test_previewing_is_what_one_click_does_unless_somebody_chose_otherwise():
    """The default is the preview. Opening on one click is the choice."""
    from backsight.engine.settings.layers import DEFAULTS

    assert DEFAULTS["files.open_on"] == "double_click"


def test_reopening_a_closed_tab_is_for_good(browsing):
    """Somebody asking for a tab back is not browsing."""
    browsing.open_file(FILES[0])
    browsing.open_in_new_tab()
    browsing.open_file(FILES[1])
    browsing._files_open.close_current()
    settle(browsing, 0.3)
    browsing.reopen_tab()
    browsing.open_file(FILES[2])
    settle(browsing, 0.3)
    assert len(tabs(browsing)) == 3


def test_turning_the_reuse_off_gives_every_file_its_own_tab(browsing):
    """It is a setting, and somebody who wants twenty tabs may have them."""
    from backsight.engine.settings.layers import DEFAULTS, Settings

    browsing.settings = Settings(
        layers={"default": dict(DEFAULTS), "user": {"files.preview_tabs": False}}
    )
    browsing._files_open.settings = browsing.settings
    browsing.open_file(FILES[0])
    browsing.open_file(FILES[1])
    settle(browsing, 0.3)
    assert len(tabs(browsing)) == 2
