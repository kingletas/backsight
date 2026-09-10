"""Verdicts land on the line that caused them, or they are not shown at all."""

from backsight.engine.insight.source_map import SourceMap
from backsight.engine.insight.verdicts import for_plan, in_file
from backsight.engine.plan.model import parse
from backsight.engine.workspace.discovery import discover

SOURCE = (
    'resource "aws_instance" "api" {\n'
    '  ami           = "ami-0123"\n'
    '  instance_type = "m6i.2xlarge"\n'
    "}\n"
    "\n"
    'resource "aws_security_group" "db" {\n'
    '  name = "db"\n'
    "}\n"
)


def plan_of(*changes):
    return parse(
        {
            "format_version": "1.2",
            "terraform_version": "1.12.6",
            "resource_changes": list(changes),
        }
    )


def change(address, actions, replace_paths=None, type_="aws_instance", name="api"):
    body = {"actions": actions}
    if replace_paths:
        body["replace_paths"] = replace_paths
    return {
        "address": address,
        "type": type_,
        "name": name,
        "mode": "managed",
        "provider_name": "aws",
        "change": body,
    }


def mapped(tmp_path):
    (tmp_path / "main.tf").write_text(SOURCE)
    workspace = discover(tmp_path)
    return SourceMap.build(workspace, workspace.root_modules[0])


def test_a_replacement_hangs_off_the_argument_that_caused_it(tmp_path):
    """Not off line 1. A verdict on the block is one the author has to hunt for."""
    found = for_plan(
        plan_of(change("aws_instance.api", ["delete", "create"], [["instance_type"]])),
        mapped(tmp_path),
    )
    assert len(found) == 1
    assert found[0].line == 3
    assert found[0].text == "Forces replacement — instance_type"
    assert found[0].tone == "replace"
    assert found[0].is_warning is True


def test_a_creation_hangs_off_the_block(tmp_path):
    found = for_plan(plan_of(change("aws_instance.api", ["create"])), mapped(tmp_path))
    assert found[0].line == 1
    assert found[0].text == "Add"
    assert found[0].is_warning is False


def test_a_destroy_says_so_in_words(tmp_path):
    found = for_plan(plan_of(change("aws_instance.api", ["delete"])), mapped(tmp_path))
    assert found[0].text == "Destroyed by this change"
    assert found[0].is_warning is True


def test_a_replacement_with_no_named_cause_says_that_rather_than_guessing(tmp_path):
    found = for_plan(plan_of(change("aws_instance.api", ["delete", "create"])), mapped(tmp_path))
    assert "does not say which attribute" in found[0].text
    assert found[0].line == 1


def test_a_change_declared_somewhere_else_gets_no_verdict(tmp_path):
    """A marker on a guessed line sends somebody to edit the wrong thing."""
    found = for_plan(
        plan_of(change("aws_instance.elsewhere", ["delete"], name="elsewhere")),
        mapped(tmp_path),
    )
    assert found == []


def test_a_no_op_gets_no_verdict(tmp_path):
    found = for_plan(plan_of(change("aws_instance.api", ["no-op"])), mapped(tmp_path))
    assert found == []


def test_verdicts_come_back_in_file_and_line_order(tmp_path):
    found = for_plan(
        plan_of(
            change("aws_security_group.db", ["delete"], type_="aws_security_group", name="db"),
            change("aws_instance.api", ["create"]),
        ),
        mapped(tmp_path),
    )
    assert [v.line for v in found] == [1, 6]


def test_only_the_open_file_is_asked_for(tmp_path):
    found = for_plan(plan_of(change("aws_instance.api", ["create"])), mapped(tmp_path))
    assert in_file(found, tmp_path / "main.tf") == found
    assert in_file(found, tmp_path / "other.tf") == []


def test_a_verdict_survives_the_file_being_unreadable(tmp_path):
    """Planned, then the file moved. The block line is still worth showing."""
    source_map = mapped(tmp_path)
    (tmp_path / "main.tf").unlink()
    found = for_plan(
        plan_of(change("aws_instance.api", ["delete", "create"], [["instance_type"]])),
        source_map,
    )
    assert len(found) == 1
    assert found[0].line == 1


def test_a_resource_inside_a_module_is_anchored_in_the_module_file(tmp_path):
    (tmp_path / "main.tf").write_text('module "vpc" {\n  source = "./vpc"\n}\n')
    inner = tmp_path / "vpc"
    inner.mkdir()
    (inner / "main.tf").write_text(
        '\nresource "aws_vpc" "this" {\n  cidr_block = "10.0.0.0/16"\n}\n'
    )
    workspace = discover(tmp_path)
    source_map = SourceMap.build(workspace, workspace.root_modules[0])
    found = for_plan(
        plan_of(change("module.vpc.aws_vpc.this", ["delete"], type_="aws_vpc", name="this")),
        source_map,
    )
    assert found[0].path.parent.name == "vpc"
    assert found[0].line == 2


def test_a_verdict_carries_the_address_so_a_row_can_link_back(tmp_path):
    found = for_plan(plan_of(change("aws_instance.api", ["create"])), mapped(tmp_path))
    assert found[0].address == "aws_instance.api"
