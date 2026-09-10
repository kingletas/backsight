"""Stack definitions parse, validate and graph entirely offline — FR-STK-09."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.stacks.model import Definitions, location, parse, read

ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "stacks"


def problems(definitions: Definitions) -> list[str]:
    return [str(problem) for problem in definitions.problems]


def test_a_workspace_with_no_stack_file_is_not_a_problem(tmp_path: Path):
    """Stacks are opt-in. Complaining about their absence would be noise."""
    found = read(tmp_path)
    assert found.stacks == {}
    assert found.problems == []
    assert not found.is_declared


def test_every_stack_in_the_file_is_read():
    found = read(ROOT / "plain")
    assert sorted(found.stacks) == ["api", "data", "edge", "network"]
    assert found.ok


def test_a_stack_carries_its_whole_identity():
    """FR-STK-01: a stack is a deployable unit, not a folder."""
    network = read(ROOT / "plain").get("network")
    assert network is not None
    assert network.path == "infra/network"
    assert network.engine == "tofu"
    assert network.backend == "s3"
    assert network.environment == "prod"
    assert network.binding.is_stated
    assert "eu-west-1" in str(network.binding)


def test_an_unstated_binding_is_unstated_rather_than_guessed():
    """Inventing a plausible account is how somebody applies to the wrong one."""
    alone = read(ROOT / "cyclic").get("alone")
    assert alone is not None
    assert not alone.binding.is_stated
    assert str(alone.binding) == ""


def test_edges_are_read_as_declared():
    """FR-STK-02: declared, never inferred."""
    api = read(ROOT / "plain").get("api")
    assert api is not None
    assert api.upstream == ("data", "network")
    assert api.needs["network"] == ("private_subnets",)


def test_consuming_an_output_the_producer_hides_is_caught_at_parse_time():
    """FR-STK-03: here, not as a plan failure twenty minutes later."""
    found = read(ROOT / "broken")
    assert any("does not publish" in said for said in problems(found))


def test_needing_a_stack_that_does_not_exist_is_reported():
    assert any("is not declared" in said for said in problems(read(ROOT / "broken")))


def test_a_stack_with_no_path_is_not_a_deployable_unit():
    found = read(ROOT / "broken")
    assert "no_path" not in found.stacks
    assert any("has no path" in said for said in problems(found))


def test_one_bad_stack_does_not_hide_the_others():
    """A typo in one edge must not take the whole graph off the screen."""
    found = read(ROOT / "broken")
    assert "good" in found.stacks
    assert found.problems


def test_a_file_that_is_not_valid_toml_says_so_rather_than_raising(tmp_path: Path):
    path = location(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("[stacks\nthis is not toml", encoding="utf-8")
    found = read(tmp_path)
    assert found.stacks == {}
    assert any("not valid" in said for said in problems(found))


def test_a_file_with_no_stacks_table_says_which_table_is_missing(tmp_path: Path):
    path = location(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("[something_else]\nkey = 1\n", encoding="utf-8")
    assert any("[stacks]" in said for said in problems(read(tmp_path)))


def test_a_stack_that_is_not_a_table_is_reported_by_name():
    assert any("is not a table" in said for said in problems(parse({"stacks": {"x": 3}})))


def test_a_file_belongs_to_the_deepest_stack_that_contains_it():
    """`infra` and `infra/network` both contain it; the answer is the specific one."""
    found = read(ROOT / "plain")
    root = ROOT / "plain"
    stack = found.containing(root / "infra" / "network" / "main.tf")
    assert stack is not None
    assert stack.name == "network"


def test_a_file_outside_every_stack_belongs_to_none():
    found = read(ROOT / "plain")
    assert found.containing(Path("/elsewhere/main.tf")) is None
