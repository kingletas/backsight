"""Searching reads what is on disk, and never walks into a cache."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.workspace.search import files_named, text_in

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "stacks" / "plain"


def test_a_file_is_found_by_part_of_its_name():
    assert [path.name for path in files_named(ROOT, "main")] == ["main.tf"] * 4


def test_searching_for_nothing_finds_nothing():
    assert files_named(ROOT, "   ") == []
    assert text_in(ROOT, "") == []


def test_text_is_found_with_the_line_it_is_on():
    found = text_in(ROOT, "terraform_data")
    assert found
    assert all(hit.line > 0 for hit in found)
    assert all("terraform_data" in hit.text for hit in found)


def test_case_is_ignored_until_asked_for():
    assert text_in(ROOT, "TERRAFORM_DATA")
    assert not text_in(ROOT, "TERRAFORM_DATA", case_sensitive=True)


def test_a_regular_expression_is_honoured_when_asked_for():
    assert text_in(ROOT, r"output\s+\"vpc_id\"", regex=True)


def test_a_regular_expression_that_does_not_compile_finds_nothing(tmp_path):
    """It is something being typed, not a fault to raise."""
    assert text_in(ROOT, "unclosed [", regex=True) == []


def test_a_provider_cache_is_never_walked_into(tmp_path):
    """Hundreds of megabytes nobody wrote."""
    (tmp_path / ".terraform" / "providers").mkdir(parents=True)
    (tmp_path / ".terraform" / "providers" / "secret.tf").write_text("findme\n")
    (tmp_path / "main.tf").write_text("findme\n")
    assert [hit.path.name for hit in text_in(tmp_path, "findme")] == ["main.tf"]
    assert files_named(tmp_path, "secret") == []


def test_a_binary_file_is_skipped_rather_than_stopping_the_search(tmp_path):
    (tmp_path / "a.tf").write_bytes(b"\xff\xfe not text \x00")
    (tmp_path / "b.tf").write_text("findme\n")
    assert [hit.path.name for hit in text_in(tmp_path, "findme")] == ["b.tf"]


def test_the_limit_is_honoured(tmp_path):
    (tmp_path / "main.tf").write_text("findme\n" * 50)
    assert len(text_in(tmp_path, "findme", limit=10)) == 10


def test_only_text_files_are_read(tmp_path):
    (tmp_path / "main.tf").write_text("findme\n")
    (tmp_path / "provider.exe").write_text("findme\n")
    assert [hit.path.name for hit in text_in(tmp_path, "findme")] == ["main.tf"]
