"""Renaming through the syntax tree, and never through the text.

The failures worth catching are the ones text substitution makes silently: the
name in a comment, the name in a tag value, and an unrelated resource of another
type that happens to share it.
"""

from pathlib import Path

import pytest
from corpus import cases

from backsight.engine.refactor.edits import Edit, apply_to
from backsight.engine.refactor.rename import Rename, declaration_count, edits_for, moved_block

RENAME = Rename(resource_type="terraform_data", old_name="api", new_name="api_gateway")


def rewrite(sources: dict[str, str], rename: Rename = RENAME) -> dict[str, str]:
    files = {Path(name): text.encode("utf-8") for name, text in sources.items()}
    edits = edits_for(files, rename)
    out = {}
    for path, data in files.items():
        mine = [e for e in edits if e.path == path]
        out[path.name] = apply_to(data, mine).decode("utf-8")
    return out


def test_the_declaration_is_renamed():
    before = 'resource "terraform_data" "api" {\n  input = "one"\n}\n'
    assert rewrite({"main.tf": before})["main.tf"] == (
        'resource "terraform_data" "api_gateway" {\n  input = "one"\n}\n'
    )


def test_a_reference_is_renamed():
    before = (
        'resource "terraform_data" "api" {}\n'
        'resource "terraform_data" "worker" {\n  input = terraform_data.api.output\n}\n'
    )
    after = rewrite({"main.tf": before})["main.tf"]
    assert "terraform_data.api_gateway.output" in after
    assert "terraform_data.api.output" not in after


def test_a_reference_in_another_file_is_renamed():
    out = rewrite(
        {
            "main.tf": 'resource "terraform_data" "api" {}\n',
            "outputs.tf": 'output "o" {\n  value = terraform_data.api.output\n}\n',
        }
    )
    assert '"api_gateway"' in out["main.tf"]
    assert "terraform_data.api_gateway.output" in out["outputs.tf"]


def test_the_name_in_a_comment_is_left_alone():
    before = '# terraform_data.api is the gateway\nresource "terraform_data" "api" {}\n'
    after = rewrite({"main.tf": before})["main.tf"]
    assert after.startswith("# terraform_data.api is the gateway\n")
    assert '"api_gateway"' in after


def test_the_name_inside_a_string_is_left_alone():
    before = 'resource "terraform_data" "api" {\n  input = "terraform_data.api"\n}\n'
    after = rewrite({"main.tf": before})["main.tf"]
    assert '"terraform_data.api"' in after
    assert 'resource "terraform_data" "api_gateway"' in after


def test_a_different_resource_type_with_the_same_name_is_left_alone():
    before = (
        'resource "terraform_data" "api" {}\n'
        'resource "null_resource" "api" {}\n'
        'output "o" {\n  value = null_resource.api.id\n}\n'
    )
    after = rewrite({"main.tf": before})["main.tf"]
    assert 'resource "null_resource" "api" {}' in after
    assert "null_resource.api.id" in after
    assert 'resource "terraform_data" "api_gateway"' in after


def test_a_data_source_and_a_resource_of_the_same_name_are_distinct():
    before = (
        'data "terraform_data" "api" {}\n'
        'resource "terraform_data" "api" {}\n'
        'output "o" {\n  value = data.terraform_data.api.id\n}\n'
    )
    after = rewrite({"main.tf": before})["main.tf"]
    assert 'data "terraform_data" "api" {}' in after
    assert "data.terraform_data.api.id" in after
    assert 'resource "terraform_data" "api_gateway"' in after


def test_everything_outside_the_edit_is_byte_identical():
    """The property the whole approach exists for."""
    before = (
        "# a header\n\n\n"
        'resource "terraform_data" "api" {\n'
        '\tinput   =    "one"\n'
        "}\n\n\n"
        "# a footer with trailing space   \n"
    )
    after = rewrite({"main.tf": before})["main.tf"]
    assert after == before.replace('"api"', '"api_gateway"', 1)


def test_a_rename_to_the_same_name_is_refused():
    with pytest.raises(ValueError, match="the new name is the old name"):
        Rename(resource_type="terraform_data", old_name="api", new_name="api")


def test_a_rename_with_no_new_name_is_refused():
    with pytest.raises(ValueError, match="needs a new name"):
        Rename(resource_type="terraform_data", old_name="api", new_name="")


def test_the_moved_block_is_written_so_it_can_be_read_and_argued_with():
    assert moved_block(RENAME) == (
        "\nmoved {\n  from = terraform_data.api\n  to   = terraform_data.api_gateway\n}\n"
    )


def test_a_data_source_moved_block_keeps_the_prefix():
    rename = Rename("aws_ami", "old", "new", kind="data")
    assert "from = data.aws_ami.old" in moved_block(rename)


def test_an_address_that_is_not_declared_here_is_countable_as_zero():
    files = {Path("main.tf"): b'resource "terraform_data" "other" {}\n'}
    assert declaration_count(files, RENAME) == 0


def test_two_edits_over_the_same_bytes_are_refused():
    with pytest.raises(ValueError, match="overlap"):
        apply_to(b"abcdef", [Edit(Path("x"), 1, 4, "X"), Edit(Path("x"), 2, 5, "Y")])


def test_an_edit_with_a_backwards_span_is_refused():
    with pytest.raises(ValueError, match="forward span"):
        Edit(Path("x"), 5, 2, "oops")


@pytest.mark.parametrize("case", [c for c in cases() if c.kind == "rename"], ids=lambda c: c.name)
def test_the_corpus_rename_cases_produce_their_expected_output(case):
    """The rename half. The moved block is appended by the caller, so the
    comparison is against the expected output with that block removed."""
    if case.name == "moved-block-pointing-at-nothing":
        pytest.skip("its moved block is deliberately wrong; the rename check refuses it")
    files = {p.relative_to(case.before): p.read_bytes() for p in case.before.rglob("*.tf")}
    edits = edits_for(files, RENAME)
    for relative, data in files.items():
        produced = apply_to(data, [e for e in edits if e.path == relative]).decode()
        expected = (case.after / relative).read_text()
        without_moved = expected.split("\nmoved {")[0]
        assert produced.rstrip("\n") == without_moved.rstrip("\n"), relative
