"""What was reached for last, so the palette opens on it rather than blank."""

from __future__ import annotations

from backsight.engine.settings.recents import MOST, read, remember


def test_nothing_used_yet_is_an_empty_list(tmp_path):
    assert read(tmp_path) == []


def test_what_was_chosen_comes_back_first(tmp_path):
    remember("plan", home=tmp_path)
    remember("apply", home=tmp_path)
    assert read(tmp_path) == ["apply", "plan"]


def test_choosing_one_again_moves_it_rather_than_repeating(tmp_path):
    """Two rows for one command is the list being wrong about what it holds."""
    remember("plan", home=tmp_path)
    remember("apply", home=tmp_path)
    remember("plan", home=tmp_path)
    assert read(tmp_path) == ["plan", "apply"]


def test_it_stays_short(tmp_path):
    """A list of thirty recents is a second wall."""
    for number in range(MOST + 5):
        remember(f"command-{number}", home=tmp_path)
    assert len(read(tmp_path)) == MOST


def test_an_empty_action_is_not_remembered(tmp_path):
    remember("   ", home=tmp_path)
    assert read(tmp_path) == []


def test_a_file_that_will_not_read_is_an_empty_list(tmp_path):
    from backsight.engine.settings.recents import FILE, directory

    where = directory(tmp_path)
    where.mkdir(parents=True)
    (where / FILE).write_text("{ not a list", encoding="utf-8")
    assert read(tmp_path) == []


def test_a_list_that_cannot_be_written_never_loses_the_command(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    assert remember("plan", home=blocked) == ["plan"]
