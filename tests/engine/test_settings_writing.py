"""Changing a setting, and leaving everything else in the file alone."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from backsight.engine.settings.writing import forget, remember, user_file


def written(home: Path) -> dict:
    return tomllib.loads(user_file(home).read_text(encoding="utf-8"))


def test_a_setting_can_be_changed_at_all(tmp_path: Path):
    remember("editor.word_wrap", True, home=tmp_path)
    assert written(tmp_path) == {"editor": {"word_wrap": True}}


def test_a_dotted_key_becomes_a_table(tmp_path: Path):
    remember("tabs.indicators.unsaved", "dot", home=tmp_path)
    assert written(tmp_path)["tabs"]["indicators"]["unsaved"] == "dot"


def test_it_leaves_every_other_line_alone(tmp_path: Path):
    remember("editor.word_wrap", True, home=tmp_path)
    remember("terraform.binary", "terraform", home=tmp_path)
    stored = written(tmp_path)
    assert stored["editor"]["word_wrap"] is True
    assert stored["terraform"]["binary"] == "terraform"


def test_changing_one_twice_keeps_the_last_answer(tmp_path: Path):
    remember("editor.tab_size", 2, home=tmp_path)
    remember("editor.tab_size", 8, home=tmp_path)
    assert written(tmp_path)["editor"]["tab_size"] == 8


def test_forgetting_lets_the_layer_below_decide_again(tmp_path: Path):
    remember("editor.word_wrap", True, home=tmp_path)
    remember("editor.tab_size", 2, home=tmp_path)
    forget("editor.word_wrap", home=tmp_path)
    assert written(tmp_path) == {"editor": {"tab_size": 2}}


def test_an_empty_table_goes_with_the_last_key_in_it(tmp_path: Path):
    """`[editor]` alone reads as a setting somebody meant to make."""
    remember("editor.word_wrap", True, home=tmp_path)
    forget("editor.word_wrap", home=tmp_path)
    assert written(tmp_path) == {}


def test_forgetting_something_never_set_is_not_an_error(tmp_path: Path):
    forget("editor.word_wrap", home=tmp_path)
    assert written(tmp_path) == {}


def test_a_file_that_will_not_parse_is_never_overwritten(tmp_path: Path):
    """The caller asked to change one key, not to discard the whole file."""
    path = user_file(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("this is not toml = = =", encoding="utf-8")
    with pytest.raises(ValueError):
        remember("editor.word_wrap", True, home=tmp_path)
    assert path.read_text(encoding="utf-8") == "this is not toml = = ="


def test_it_never_writes_the_workspace_file(tmp_path: Path):
    """That one is committed and shared; a checkbox may not edit a colleague's."""
    remember("editor.word_wrap", True, home=tmp_path)
    assert not (tmp_path / ".backsight").exists()
    assert user_file(tmp_path).parts[-3:] == (".config", "backsight", "settings.toml")


def test_the_write_leaves_nothing_half_finished(tmp_path: Path):
    remember("editor.word_wrap", True, home=tmp_path)
    beside = list(user_file(tmp_path).parent.glob("*.writing"))
    assert beside == []
