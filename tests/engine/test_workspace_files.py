"""Nothing here deletes, and nothing here overwrites."""

from __future__ import annotations

import pytest

from backsight.engine.workspace.files import (
    Refused,
    create,
    create_folder,
    duplicate,
    move,
    remove,
    rename,
)


def test_creating_a_file_that_exists_is_refused(tmp_path):
    (tmp_path / "main.tf").write_text("original\n")
    with pytest.raises(Refused):
        create(tmp_path / "main.tf")
    assert (tmp_path / "main.tf").read_text() == "original\n"


def test_creating_makes_the_directories_it_needs(tmp_path):
    made = create(tmp_path / "modules" / "net" / "main.tf")
    assert made.is_file()


def test_renaming_onto_an_existing_file_is_refused(tmp_path):
    (tmp_path / "a.tf").write_text("a\n")
    (tmp_path / "b.tf").write_text("b\n")
    with pytest.raises(Refused):
        rename(tmp_path / "a.tf", "b.tf")
    assert (tmp_path / "b.tf").read_text() == "b\n"


def test_a_name_with_a_slash_in_it_is_not_a_name(tmp_path):
    """Renaming is within a directory; a path would move the file silently."""
    (tmp_path / "a.tf").write_text("a\n")
    with pytest.raises(Refused):
        rename(tmp_path / "a.tf", "../escaped.tf")


def test_renaming_to_the_same_name_changes_nothing(tmp_path):
    path = tmp_path / "a.tf"
    path.write_text("a\n")
    assert rename(path, "a.tf") == path


def test_duplicating_finds_a_name_nothing_has(tmp_path):
    path = tmp_path / "main.tf"
    path.write_text("body\n")
    first = duplicate(path)
    second = duplicate(path)
    assert first.name == "main copy.tf"
    assert second.name == "main copy 2.tf"
    assert first.read_text() == "body\n"


def test_moving_onto_an_existing_file_is_refused(tmp_path):
    (tmp_path / "a.tf").write_text("a\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.tf").write_text("theirs\n")
    with pytest.raises(Refused):
        move(tmp_path / "a.tf", tmp_path / "sub")
    assert (tmp_path / "sub" / "a.tf").read_text() == "theirs\n"


def test_removing_goes_to_the_trash_rather_than_deleting(tmp_path):
    path = tmp_path / "main.tf"
    path.write_text("body\n")
    trashed: list = []
    removed = remove(path, to_trash=trashed.append)
    assert removed.trashed
    assert trashed == [path]


def test_a_trash_that_fails_leaves_the_file_where_it_is(tmp_path):
    """No fallback: "move to trash" must never quietly become "delete"."""
    path = tmp_path / "main.tf"
    path.write_text("body\n")

    def refuse(_path):
        raise RuntimeError("no trash on this filesystem")

    with pytest.raises(Refused, match="left where it is"):
        remove(path, to_trash=refuse)
    assert path.read_text() == "body\n"


def test_removing_something_that_is_not_there_says_so(tmp_path):
    with pytest.raises(Refused):
        remove(tmp_path / "nothing.tf", to_trash=lambda _p: None)


def test_creating_a_folder_that_exists_is_refused(tmp_path):
    (tmp_path / "sub").mkdir()
    with pytest.raises(Refused):
        create_folder(tmp_path / "sub")
