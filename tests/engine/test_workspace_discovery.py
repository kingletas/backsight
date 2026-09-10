"""Opening a directory, and what reading it should say about it."""

from pathlib import Path

import pytest

from backsight.engine.workspace.discovery import discover

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures" / "workspace"


@pytest.fixture(scope="module")
def workspace():
    return discover(FIXTURE)


def test_every_directory_with_terraform_in_it_is_a_module(workspace):
    names = sorted(m.path.relative_to(FIXTURE).as_posix() for m in workspace.modules)
    assert names == ["environments/prod", "environments/staging", "modules/vpc"]


def test_a_module_somebody_calls_is_not_a_root_module(workspace):
    roots = sorted(m.path.relative_to(FIXTURE).as_posix() for m in workspace.root_modules)
    assert roots == ["environments/prod", "environments/staging"]
    assert workspace.module_at(FIXTURE / "modules" / "vpc").is_root is False


def test_a_directory_with_no_terraform_is_not_a_module(workspace):
    assert workspace.module_at(FIXTURE / "docs") is None


def test_the_download_cache_is_not_searched(workspace):
    """A module inside `.terraform` is a copy of one already listed."""
    assert all(".terraform" not in m.path.parts for m in workspace.modules)


def test_opening_a_directory_with_no_terraform_says_so(tmp_path):
    (tmp_path / "notes.md").write_text("nothing here")
    found = discover(tmp_path)
    assert found.is_terraform is False
    assert found.modules == []


def test_the_backend_is_read_from_the_terraform_block(workspace):
    assert workspace.module_at(FIXTURE / "environments" / "prod").backend == "s3"


def test_a_module_with_no_backend_block_reports_none(workspace):
    assert workspace.module_at(FIXTURE / "environments" / "staging").backend is None


def test_provider_requirements_are_read(workspace):
    prod = workspace.module_at(FIXTURE / "environments" / "prod")
    assert [p.name for p in prod.providers] == ["aws", "random"]
    aws = prod.provider("aws")
    assert aws.source == "hashicorp/aws"
    assert aws.constraint == "~> 5.82"


def test_the_lock_file_supplies_the_version_actually_in_use(workspace):
    """The constraint is a range. Only the lock file says which version it is."""
    prod = workspace.module_at(FIXTURE / "environments" / "prod")
    assert prod.has_lock_file
    assert prod.provider("aws").locked_version == "5.82.2"
    assert prod.provider("random").locked_version == "3.6.3"


def test_a_module_with_no_lock_file_has_no_locked_version(workspace):
    staging = workspace.module_at(FIXTURE / "environments" / "staging")
    assert staging.has_lock_file is False
    assert staging.provider("aws").constraint == "~> 5.82"
    assert staging.provider("aws").locked_version is None


def test_tfvars_are_listed_alongside_tf_files(workspace):
    prod = workspace.module_at(FIXTURE / "environments" / "prod")
    assert [p.name for p in prod.files] == ["main.tf", "terraform.tfvars", "variables.tf"]


def test_a_backend_written_in_a_comment_is_not_a_backend(tmp_path):
    """The reason this reads the syntax tree instead of matching text."""
    (tmp_path / "main.tf").write_text(
        '# terraform {\n#   backend "s3" {}\n# }\n\nresource "null_resource" "a" {}\n'
    )
    module = discover(tmp_path).modules[0]
    assert module.backend is None


def test_a_registry_module_never_makes_a_local_directory_a_child(tmp_path):
    (tmp_path / "main.tf").write_text(
        'module "vpc" {\n  source = "terraform-aws-modules/vpc/aws"\n}\n'
    )
    assert discover(tmp_path).modules[0].is_root is True


def test_a_file_that_opens_with_a_comment_still_has_its_blocks_read(tmp_path):
    """Leading comments sit beside the body, not inside it."""
    (tmp_path / "main.tf").write_text(
        '# managed by the platform team\n# do not edit\nterraform {\n  backend "local" {}\n}\n'
    )
    assert discover(tmp_path).modules[0].backend == "local"


def test_a_module_that_calls_itself_is_still_a_root_module(tmp_path):
    """Otherwise a workspace with a recursive module has no root at all."""
    (tmp_path / "main.tf").write_text('module "self" {\n  source = "."\n}\n')
    found = discover(tmp_path)
    assert len(found.root_modules) == 1
