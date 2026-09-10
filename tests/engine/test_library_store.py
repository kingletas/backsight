"""Where entries come from, and which wins when two share a name."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.library.entry import Entry, Kind, Source
from backsight.engine.library.store import (
    SHIPPED,
    Library,
    in_workspace,
    load,
    read_directory,
    save,
    yours,
)

# What ships with the application is always there, so a test about the other
# sources asks what they added rather than what the whole library holds.
SHIPPED_NAMES = {entry.name for entry in read_directory(SHIPPED, Source.BUILT_IN)[0]}


def added_by(found: Library) -> list[str]:
    return sorted(entry.name for entry in found.entries if entry.name not in SHIPPED_NAMES)


def an_entry(name: str, **rest) -> Entry:
    return Entry(name=name, body='resource "a" "b" {}\n', **rest)


def put(where: Path, name: str, body: str = 'resource "a" "b" {}\n', kind: str = "snippet") -> Path:
    where.mkdir(parents=True, exist_ok=True)
    path = where / f"{name.lower().replace(' ', '-')}.tf"
    path.write_text(f"# name: {name}\n# kind: {kind}\n\n{body}", encoding="utf-8")
    return path


def test_an_empty_machine_still_has_what_ships(tmp_path):
    """A library with nothing in it is a mechanism rather than a feature."""
    found = load(home=tmp_path)
    assert isinstance(found, Library)
    assert added_by(found) == []
    assert len(found) >= 10
    assert found.broken == []


def test_it_reads_your_own_entries(tmp_path):
    put(yours(tmp_path), "Private bucket")
    found = load(home=tmp_path)
    assert added_by(found) == ["Private bucket"]
    assert found.named("Private bucket").source is Source.YOURS


def test_a_workspace_carries_its_own(tmp_path):
    workspace = tmp_path / "repo"
    put(in_workspace(workspace), "House bucket")
    found = load(home=tmp_path, workspace=workspace)
    assert found.named("House bucket").source is Source.WORKSPACE


def test_your_copy_wins_over_the_workspace_and_the_shared_one(tmp_path):
    """Overriding something you were given must not mean arguing with it."""
    workspace = tmp_path / "repo"
    shared = tmp_path / "shared"
    put(shared, "Bucket", body="# shared\n")
    put(in_workspace(workspace), "Bucket", body="# workspace\n")
    put(yours(tmp_path), "Bucket", body="# yours\n")
    found = load(home=tmp_path, workspace=workspace, shared=shared)
    assert added_by(found) == ["Bucket"]
    assert found.named("Bucket").source is Source.YOURS
    assert "# yours" in found.named("Bucket").body


def test_the_workspace_wins_over_shared(tmp_path):
    workspace = tmp_path / "repo"
    shared = tmp_path / "shared"
    put(shared, "Bucket", body="# shared\n")
    put(in_workspace(workspace), "Bucket", body="# workspace\n")
    found = load(home=tmp_path, workspace=workspace, shared=shared)
    assert found.named("Bucket").source is Source.WORKSPACE


def test_anything_written_by_hand_wins_over_a_generated_one(tmp_path):
    generated = [an_entry("aws_s3_bucket — required only", source=Source.BUILT_IN)]
    put(yours(tmp_path), "aws_s3_bucket — required only", body="# mine\n")
    found = load(home=tmp_path, generated=generated)
    assert found.named("aws_s3_bucket — required only").source is Source.YOURS


def test_a_file_that_will_not_read_is_reported_rather_than_skipped(tmp_path):
    where = yours(tmp_path)
    where.mkdir(parents=True)
    (where / "broken.tf").write_text('resource "a" "b" {}\n', encoding="utf-8")
    put(where, "Good one")
    found = load(home=tmp_path)
    assert added_by(found) == ["Good one"]
    assert len(found.broken) == 1
    assert found.broken[0].path.name == "broken.tf"


def test_entries_nest_in_folders(tmp_path):
    put(yours(tmp_path) / "aws" / "storage", "Deep one")
    assert "Deep one" in added_by(load(home=tmp_path))


def test_a_directory_that_is_not_there_is_not_a_failure(tmp_path):
    entries, broken = read_directory(tmp_path / "nope", Source.SHARED)
    assert entries == [] and broken == []


# --- finding one -----------------------------------------------------------


def a_library() -> Library:
    return Library(
        entries=[
            an_entry("Private bucket", tags=("s3", "storage"), resource="aws_s3_bucket"),
            an_entry("Bucket policy", tags=("s3", "iam"), resource="aws_s3_bucket_policy"),
            an_entry("Rotate a password", kind=Kind.RUNBOOK, tags=("rds",)),
        ]
    )


def test_a_name_that_starts_with_what_you_typed_comes_first():
    found = a_library().search("bucket")
    assert found[0].name == "Bucket policy"


def test_searching_reaches_tags_and_the_resource_type():
    assert [entry.name for entry in a_library().search("s3")] == [
        "Bucket policy",
        "Private bucket",
    ]
    assert a_library().search("aws_s3_bucket_policy")[0].name == "Bucket policy"


def test_a_kind_can_be_asked_for_on_its_own():
    found = a_library().search(kind=Kind.RUNBOOK)
    assert [entry.name for entry in found] == ["Rotate a password"]


def test_everything_about_one_resource_answers_from_the_cursor():
    found = a_library().for_resource("aws_s3_bucket")
    assert [entry.name for entry in found] == ["Private bucket"]


def test_it_counts_what_it_has_of_each_kind():
    assert a_library().kinds == {Kind.SNIPPET: 2, Kind.RUNBOOK: 1}


# --- saving ----------------------------------------------------------------


def test_saving_puts_yours_where_yours_live_and_comes_back(tmp_path):
    path = save(an_entry("My bucket", about="Mine"), home=tmp_path)
    assert path.parent == yours(tmp_path)
    again = load(home=tmp_path)
    assert again.named("My bucket").about == "Mine"


def test_saving_a_workspace_entry_puts_it_with_the_code(tmp_path):
    workspace = tmp_path / "repo"
    path = save(an_entry("House rule", source=Source.WORKSPACE), home=tmp_path, workspace=workspace)
    assert path.parent == in_workspace(workspace)


def test_saving_twice_replaces_rather_than_accumulating(tmp_path):
    save(an_entry("Same name", about="first"), home=tmp_path)
    save(an_entry("Same name", about="second"), home=tmp_path)
    found = load(home=tmp_path)
    assert added_by(found) == ["Same name"]
    assert found.named("Same name").about == "second"
