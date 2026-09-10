"""Moving resources into a module without destroying them.

Terraform matches state on the address, and a resource that moves into a module
gets a new one. Without a `moved` block the plan is a destroy and a create,
which for anything holding data is the worst outcome in the tool.
"""

from __future__ import annotations

from pathlib import Path

from backsight.engine.hcl.navigation import blocks
from backsight.engine.refactor.edits import apply_to
from backsight.engine.refactor.extract import extract, is_a_name, moved_blocks, proposal_for

SOURCE = """variable "name" {
  type = string
}

resource "terraform_data" "vpc" {
  input = var.name
}

resource "terraform_data" "subnet" {
  input = terraform_data.vpc.output
}

output "id" {
  value = terraform_data.vpc.output
}
"""


def an_extraction(*addresses, module="network"):
    return extract(Path("main.tf"), SOURCE, tuple(addresses), module=module, relative_to=Path())


def test_it_moves_the_blocks_that_were_asked_for():
    found = an_extraction("terraform_data.vpc", "terraform_data.subnet")
    assert found is not None
    assert found.addresses == ("terraform_data.vpc", "terraform_data.subnet")


def test_every_address_gets_a_moved_block():
    """The point of the whole refactor."""
    said = moved_blocks("network", ("terraform_data.vpc", "terraform_data.subnet"))
    assert "from = terraform_data.vpc" in said
    assert "to   = module.network.terraform_data.vpc" in said
    assert said.count("moved {") == 2


def test_the_moved_blocks_are_terraform_that_parses():
    said = moved_blocks("network", ("terraform_data.vpc",))
    assert blocks(said.encode("utf-8"))


def test_what_is_left_behind_no_longer_declares_them():
    found = an_extraction("terraform_data.vpc")
    left = apply_to(SOURCE.encode("utf-8"), list(found.edits)).decode("utf-8")
    remaining = {block.address for block in blocks(left.encode("utf-8"))}
    assert "terraform_data.vpc" not in remaining
    assert "terraform_data.subnet" in remaining


def test_the_module_gets_the_blocks_verbatim():
    found = an_extraction("terraform_data.vpc")
    into = found.appended[Path("network") / "main.tf"]
    assert 'resource "terraform_data" "vpc"' in into
    assert "input = var.name" in into
    assert blocks(into.encode("utf-8"))


def test_the_file_gains_a_call_and_the_moved_blocks():
    found = an_extraction("terraform_data.vpc")
    added = found.appended[Path("main.tf")]
    assert 'module "network"' in added
    assert 'source = "./network"' in added
    assert "moved {" in added
    assert blocks(added.encode("utf-8"))


def test_the_whole_file_still_parses_afterwards():
    found = an_extraction("terraform_data.vpc")
    left = apply_to(SOURCE.encode("utf-8"), list(found.edits)).decode("utf-8")
    whole = left + found.appended[Path("main.tf")]
    assert blocks(whole.encode("utf-8"))


def test_a_source_can_be_given_rather_than_a_relative_path():
    found = extract(
        Path("main.tf"),
        SOURCE,
        ("terraform_data.vpc",),
        module="network",
        relative_to=Path(),
        source="git::https://example.invalid/modules//network",
    )
    assert "git::https://example.invalid/modules//network" in found.appended[Path("main.tf")]


def test_an_address_that_is_not_in_the_file_extracts_nothing():
    """Cutting a hole in one file and writing the wrong thing into a module."""
    assert an_extraction("terraform_data.nowhere") is None
    assert an_extraction("terraform_data.vpc", "terraform_data.nowhere") is None


def test_nothing_asked_for_is_nothing_done():
    assert an_extraction() is None


def test_a_module_needs_a_name():
    assert an_extraction("terraform_data.vpc", module="  ") is None


def test_the_same_address_twice_is_moved_once():
    found = an_extraction("terraform_data.vpc", "terraform_data.vpc")
    assert found.addresses == ("terraform_data.vpc",)
    assert len(found.edits) == 1


def test_it_becomes_something_the_gate_can_verify():
    """Nothing here decides whether it is safe — the gate plans it and refuses
    anything destructive."""
    proposal = proposal_for(an_extraction("terraform_data.vpc"))
    assert proposal.description.startswith("Extract 1 resource")
    assert proposal.edits
    assert proposal.appended


def test_a_module_name_has_to_be_a_terraform_identifier():
    assert is_a_name("network")
    assert is_a_name("shared_network")
    assert not is_a_name("2network")
    assert not is_a_name("net work")
    assert not is_a_name("")


def test_a_proposal_can_create_a_file_that_is_not_there_yet(tmp_path):
    """Extracting writes new files, and reading them first would be reading
    something nobody has written."""
    (tmp_path / "main.tf").write_text(SOURCE, encoding="utf-8")
    proposal = proposal_for(an_extraction("terraform_data.vpc"))
    written = proposal.rewrite(tmp_path)
    assert Path("network") / "main.tf" in written
    assert b'resource "terraform_data" "vpc"' in written[Path("network") / "main.tf"]
