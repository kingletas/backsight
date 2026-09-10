"""What is in the state file, read from a real one."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.workspace.backend import WITHOUT_A_BACKEND, local_state

CAPTURED = Path(__file__).resolve().parents[2] / "fixtures" / "local-state"


def test_it_reads_a_real_state_file():
    found = local_state(CAPTURED)
    assert found is not None
    assert found.resources == 2
    assert found.serial == 1
    assert found.size > 0
    assert not found.is_empty


def test_it_says_how_much_is_in_it_and_when():
    said = local_state(CAPTURED).says()
    assert said.startswith("2 resources, last written ")


def test_one_resource_is_not_one_resources(tmp_path: Path):
    (tmp_path / "terraform.tfstate").write_text('{"serial": 3, "resources": [{}]}')
    assert local_state(tmp_path).says().startswith("1 resource, ")


def test_no_state_file_is_not_an_error(tmp_path: Path):
    assert local_state(tmp_path) is None


def test_an_unreadable_one_is_treated_as_absent(tmp_path: Path):
    """A view that explains a situation cannot explain one it could not read."""
    (tmp_path / "terraform.tfstate").write_text("{ not json")
    assert local_state(tmp_path) is None


def test_a_state_file_with_nothing_in_it_says_so(tmp_path: Path):
    (tmp_path / "terraform.tfstate").write_text('{"serial": 0, "resources": []}')
    assert local_state(tmp_path).is_empty


def test_every_cost_is_a_thing_somebody_will_try_and_fail_to_do():
    """Not "some features are unavailable" — each one names what it takes away."""
    assert len(WITHOUT_A_BACKEND) >= 3
    for said in WITHOUT_A_BACKEND:
        assert said.endswith(".")
        assert "unavailable" not in said
