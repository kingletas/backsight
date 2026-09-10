"""What a tab says, and that it never says something colour alone would carry."""

from pathlib import Path

import pytest

from backsight.app.tab_marks import IMPACT_ICONS, VCS_ICONS, impact_icon, title, tooltip, vcs_icon
from backsight.engine.insight.file_status import FileStatus, Impact
from backsight.engine.vcs.git import Vcs

HERE = Path("modules/api/main.tf")


def status(**kwargs) -> FileStatus:
    return FileStatus(path=HERE, **kwargs)


def test_every_state_has_a_shape_of_its_own():
    """NFR-15. Take the colour away and a triangle is still not a trash can."""
    assert len(set(VCS_ICONS.values())) == len(VCS_ICONS)
    assert len(set(IMPACT_ICONS.values())) == len(IMPACT_ICONS)


def test_an_unchanged_file_carries_no_git_mark():
    assert vcs_icon(status(vcs=Vcs.UNCHANGED)) is None


def test_an_untouched_file_carries_no_plan_mark():
    assert impact_icon(status(impact=Impact.UNTOUCHED)) is None


def test_an_unreadable_file_shows_no_plan_mark_at_all():
    """A stale edge on a file with no meaningful plan state is worse than none."""
    assert impact_icon(status(impact=Impact.DESTROY, unreadable=True)) is None


def test_the_two_slots_are_independent():
    both = status(vcs=Vcs.UNTRACKED, impact=Impact.DESTROY)
    assert vcs_icon(both) == VCS_ICONS[Vcs.UNTRACKED]
    assert impact_icon(both) == IMPACT_ICONS[Impact.DESTROY]


def test_unsaved_shows_in_the_title():
    assert title("main.tf", status(unsaved=True)) == "main.tf •"
    assert title("main.tf", status(unsaved=False)) == "main.tf"


def test_letters_mode_puts_the_git_state_in_the_text():
    """The only carrier that survives a screenshot with no icons."""
    assert title("main.tf", status(vcs=Vcs.MODIFIED), letters=True) == "M main.tf"
    assert title("main.tf", status(vcs=Vcs.UNCHANGED), letters=True) == "main.tf"


def test_letters_and_unsaved_coexist():
    assert title("main.tf", status(vcs=Vcs.CONFLICTED, unsaved=True), letters=True) == "C main.tf •"


@pytest.mark.parametrize("state", [Vcs.UNTRACKED, Vcs.MODIFIED, Vcs.CONFLICTED, Vcs.DELETED])
def test_the_tooltip_says_the_git_state_in_words(state):
    said = tooltip(str(HERE), status(vcs=state))
    assert str(HERE) in said
    assert said.splitlines()[1]


def test_the_tooltip_carries_the_counts_the_tab_has_no_room_for():
    said = tooltip(
        str(HERE),
        status(impact=Impact.DESTROY, counts=((Impact.DESTROY, 1), (Impact.CREATE, 2))),
    )
    assert "destroys resources" in said
    assert "＋2 ▼1" in said


def test_an_unreadable_file_says_only_that():
    """It has no meaningful plan state, so nothing else is claimed about it."""
    said = tooltip(str(HERE), status(unreadable=True, impact=Impact.DESTROY))
    assert "not UTF-8" in said
    assert "destroys" not in said


def test_the_tab_hit_test_refuses_when_the_mapping_is_unsafe():
    """A libadwaita layout change must break the shortcut, not close a file.

    An unrealised bar has no per-tab widgets while the view has pages, which is
    the same mismatch a reshuffled tab box would produce.
    """
    from backsight.app.editor import Editor, _tab_under

    root = Path(__file__).resolve().parents[2] / "fixtures" / "workspace"
    editor = Editor()
    editor.open(next(iter(sorted(root.rglob("*.tf")))))
    assert editor._tabs.get_n_pages() == 1
    assert _tab_under(editor._tab_bar, editor._tabs, 10, 10) is None
