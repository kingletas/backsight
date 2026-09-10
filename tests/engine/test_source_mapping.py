"""A finding lands on the line that caused it.

FR-ED-05: a finding the author cannot locate is a finding they will not fix.
Single file, several files, and a resource nested inside called modules.
"""

from pathlib import Path

import pytest

from backsight.engine.insight.source_map import SourceMap, attribute_line
from backsight.engine.workspace.discovery import discover

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "workspace"


def mapped(directory: Path, module_name: str | None = None) -> SourceMap:
    workspace = discover(directory)
    root = (
        workspace.module_at(directory / module_name) if module_name else workspace.root_modules[0]
    )
    return SourceMap.build(workspace, root)


def test_a_resource_in_one_file_is_found(tmp_path):
    (tmp_path / "main.tf").write_text(
        '# a note\n\nresource "aws_instance" "api" {\n  instance_type = "t3.micro"\n}\n'
    )
    place = mapped(tmp_path).locate("aws_instance.api")
    assert place.path.name == "main.tf"
    assert place.line == 3


def test_a_resource_is_found_in_whichever_file_declares_it(tmp_path):
    (tmp_path / "main.tf").write_text('resource "aws_instance" "api" {}\n')
    (tmp_path / "network.tf").write_text('\n\nresource "aws_security_group" "db" {}\n')
    found = mapped(tmp_path)
    assert found.locate("aws_instance.api").path.name == "main.tf"
    place = found.locate("aws_security_group.db")
    assert place.path.name == "network.tf"
    assert place.line == 3


def test_a_data_source_keeps_its_data_prefix(tmp_path):
    (tmp_path / "main.tf").write_text('data "aws_ami" "latest" {}\n')
    assert mapped(tmp_path).locate("data.aws_ami.latest").line == 1
    assert mapped(tmp_path).locate("aws_ami.latest") is None


def test_a_resource_inside_a_called_module_is_found():
    """The plan says `module.vpc.aws_vpc.this`; the file is two directories away."""
    found = mapped(FIXTURE, "environments/prod")
    place = found.locate("module.vpc.aws_vpc.this")
    assert place is not None
    assert place.path.parent.name == "vpc"
    assert place.path.name == "main.tf"


def test_the_module_call_itself_is_found():
    found = mapped(FIXTURE, "environments/prod")
    place = found.locate("module.vpc")
    assert place.path.name == "main.tf"
    assert place.path.parent.name == "prod"


def test_a_module_nested_two_deep_is_found(tmp_path):
    (tmp_path / "main.tf").write_text('module "outer" {\n  source = "./outer"\n}\n')
    outer = tmp_path / "outer"
    outer.mkdir()
    (outer / "main.tf").write_text('module "inner" {\n  source = "./inner"\n}\n')
    inner = outer / "inner"
    inner.mkdir()
    (inner / "main.tf").write_text('resource "null_resource" "deep" {}\n')
    place = mapped(tmp_path).locate("module.outer.module.inner.null_resource.deep")
    assert place is not None
    assert place.path.parent.name == "inner"


def test_an_index_is_ignored_when_locating(tmp_path):
    """`for_each` and `count` give every instance its own address, one declaration."""
    (tmp_path / "main.tf").write_text('resource "aws_subnet" "this" {\n  count = 3\n}\n')
    found = mapped(tmp_path)
    assert found.locate("aws_subnet.this[0]").line == 1
    assert found.locate('aws_subnet.this["a"]').line == 1


def test_an_address_that_is_not_declared_here_is_not_invented(tmp_path):
    (tmp_path / "main.tf").write_text('resource "null_resource" "a" {}\n')
    assert mapped(tmp_path).locate("null_resource.b") is None


def test_an_address_written_in_a_comment_is_not_a_declaration(tmp_path):
    """The reason this reads the tree instead of searching for the text."""
    (tmp_path / "main.tf").write_text(
        '# resource "aws_instance" "ghost" {}\n'
        'resource "aws_instance" "real" {\n'
        '  tags = { note = "aws_instance.ghost" }\n'
        "}\n"
    )
    found = mapped(tmp_path)
    assert found.locate("aws_instance.ghost") is None
    assert found.locate("aws_instance.real").line == 2


def test_a_module_that_calls_itself_does_not_run_forever(tmp_path):
    (tmp_path / "main.tf").write_text(
        'module "self" {\n  source = "."\n}\nresource "null_resource" "a" {}\n'
    )
    found = mapped(tmp_path)
    assert found.locate("null_resource.a") is not None


def test_the_verdict_hangs_off_the_argument_not_the_block():
    """A finding on the top line of a resource is one the author has to hunt for."""
    source = (
        b'resource "aws_instance" "api" {\n'
        b'  ami           = "ami-0123"\n'
        b'  instance_type = "m6i.2xlarge"\n'
        b"}\n"
    )
    assert attribute_line(source, 1, "instance_type") == 3
    assert attribute_line(source, 1, "ami") == 2


def test_an_argument_inside_a_nested_block_is_found():
    source = (
        b'resource "aws_instance" "api" {\n  root_block_device {\n    volume_size = 20\n  }\n}\n'
    )
    assert attribute_line(source, 1, "volume_size") == 3


def test_an_argument_that_is_not_there_returns_nothing():
    source = b'resource "aws_instance" "api" {\n  ami = "x"\n}\n'
    assert attribute_line(source, 1, "instance_type") is None


@pytest.mark.parametrize("address", ["aws_instance.api", "data.aws_ami.x", "module.vpc"])
def test_every_kind_of_address_round_trips(tmp_path, address):
    (tmp_path / "main.tf").write_text(
        'resource "aws_instance" "api" {}\n'
        'data "aws_ami" "x" {}\n'
        'module "vpc" {\n  source = "terraform-aws-modules/vpc/aws"\n}\n'
    )
    assert mapped(tmp_path).locate(address) is not None
