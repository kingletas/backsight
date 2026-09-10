"""Block navigation reads the syntax tree, never text."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.hcl.navigation import (
    blocks,
    declaring,
    enclosing,
    end_of,
    references_in,
    start_of,
)

ROOT = Path(__file__).resolve().parents[2] / "fixtures"
SOURCE = (ROOT / "stacks" / "plain" / "infra" / "network" / "main.tf").read_bytes()


def test_every_block_is_found_with_its_span():
    found = blocks(SOURCE)
    assert [block.type for block in found] == ["resource", "output", "output", "output"]
    assert (found[0].first, found[0].last) == (3, 5)


def test_a_resource_gets_the_address_a_plan_would_use():
    assert blocks(SOURCE)[0].address == "terraform_data.vpc"


def test_a_data_source_is_addressed_with_its_prefix():
    found = blocks(b'data "aws_ami" "latest" {\n  owners = ["self"]\n}\n')
    assert found[0].address == "data.aws_ami.latest"


def test_a_block_with_no_address_says_so_rather_than_guessing():
    found = blocks(b'terraform {\n  required_version = ">= 1.0"\n}\n')
    assert found[0].address == ""


def test_the_innermost_block_wins():
    assert enclosing(SOURCE, 4).address == "terraform_data.vpc"


def test_a_line_between_blocks_is_inside_none():
    assert enclosing(SOURCE, 6) is None


def test_moving_to_the_start_from_inside_finds_this_block():
    assert start_of(SOURCE, 4) == 3


def test_moving_to_the_start_from_the_first_line_finds_the_one_before():
    """Pressing it twice must not stand still."""
    assert start_of(SOURCE, 7) == 3


def test_moving_to_the_end_from_inside_finds_this_block():
    assert end_of(SOURCE, 4) == 5


def test_moving_to_the_end_from_the_last_line_finds_the_next():
    assert end_of(SOURCE, 5) == 9


def test_before_the_first_block_there_is_nothing_earlier():
    assert start_of(SOURCE, 1) is None


def test_after_the_last_block_there_is_nothing_later():
    assert end_of(SOURCE, 99) is None


def test_a_definition_is_found_by_its_address():
    assert declaring(SOURCE, "output.vpc_id").first == 7


def test_an_address_nothing_declares_is_not_invented():
    assert declaring(SOURCE, "aws_instance.nothing") is None


def test_references_exclude_the_declaration_itself():
    assert references_in(SOURCE, "terraform_data.vpc") == [8]


def test_a_brace_inside_a_string_never_moves_the_cursor():
    """The reason this reads the tree rather than matching text."""
    source = b'resource "terraform_data" "a" {\n  input = "} not the end {"\n  x = 1\n}\n'
    assert blocks(source)[0].last == 4


def test_a_file_that_does_not_parse_yields_nothing_rather_than_raising():
    assert blocks(b'resource "unclosed" {\n') is not None
