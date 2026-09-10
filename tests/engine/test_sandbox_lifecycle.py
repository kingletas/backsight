"""Managing the emulator container, and degrading clearly when there is none."""

import json
import os
from pathlib import Path

import pytest

from backsight.engine.sandbox import runtime as runtime_module
from backsight.engine.sandbox.ministack import DEFAULT_PORT, Health, Sandbox, SandboxError
from backsight.engine.sandbox.runtime import NoRuntime, Runtime, detect, require

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures" / "ministack"

HAS_RUNTIME = detect() is not None
needs_runtime = pytest.mark.skipif(not HAS_RUNTIME, reason="no container runtime installed")
sandbox_test = pytest.mark.sandbox


# --- finding a runtime ----------------------------------------------------


def test_podman_is_preferred_over_docker(monkeypatch):
    """§9.5: rootless Podman is the one that survives confined packaging."""
    monkeypatch.setattr(runtime_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert detect().name == "podman"


def test_docker_is_used_when_podman_is_absent(monkeypatch):
    monkeypatch.setattr(
        runtime_module.shutil, "which", lambda name: "/usr/bin/docker" if name == "docker" else None
    )
    assert detect().name == "docker"


def test_no_runtime_is_an_ordinary_state_and_not_an_error(monkeypatch):
    monkeypatch.setattr(runtime_module.shutil, "which", lambda _name: None)
    assert detect() is None


def test_asking_for_a_runtime_that_is_not_there_says_what_to_install(monkeypatch):
    """FR-SIM-10: degrade with guidance, not with a file-not-found somewhere deep."""
    monkeypatch.setattr(runtime_module.shutil, "which", lambda _name: None)
    with pytest.raises(NoRuntime) as raised:
        require()
    message = str(raised.value)
    assert "neither Podman nor Docker is installed" in message
    assert "Everything else works without one" in message
    assert "apt install podman" in message


def test_only_podman_is_reported_as_rootless_capable():
    assert Runtime("podman", "/usr/bin/podman").is_rootless_capable is True
    assert Runtime("docker", "/usr/bin/docker").is_rootless_capable is False


# --- reading what the emulator says ---------------------------------------


def test_the_health_fixture_is_what_a_real_emulator_returned():
    document = json.loads((FIXTURES / "health.json").read_text())
    health = Health(
        version=document["version"], edition=document["edition"], services=document["services"]
    )
    assert health.version == "1.5.8"
    assert len(health.available) >= 60, "the emulator claims 60+ services"
    assert "ec2" in health.available and "s3" in health.available


def test_the_reset_fixture_is_what_a_real_reset_returned():
    assert json.loads((FIXTURES / "reset.txt").read_text()) == {"reset": "ok"}


def test_a_sandbox_that_is_not_answering_reports_no_health():
    """Nothing there is not the same as unhealthy, and neither is an exception."""
    sandbox = Sandbox(runtime=Runtime("docker", "/usr/bin/docker"), port=1)
    assert sandbox.health(timeout=0.2) is None


def test_waiting_for_a_sandbox_that_never_arrives_says_where_to_look():
    sandbox = Sandbox(runtime=Runtime("docker", "/usr/bin/docker"), port=1, name="nothing")
    with pytest.raises(SandboxError, match="did not become healthy"):
        sandbox.wait_until_healthy(timeout=0.5)


def test_resetting_something_that_is_not_there_is_an_error_with_a_reason():
    sandbox = Sandbox(runtime=Runtime("docker", "/usr/bin/docker"), port=1)
    with pytest.raises(SandboxError, match="Could not reset"):
        sandbox.reset()


def test_the_default_port_is_not_the_emulator_s_usual_one():
    """Taking 4566 from whatever a developer already has running would be rude."""
    assert DEFAULT_PORT != 4566


# --- against a real container ---------------------------------------------


@pytest.fixture(scope="module")
def sandbox():
    made = Sandbox(name=f"backsight-test-sandbox-{os.getpid()}", port=15000 + os.getpid() % 300)
    made.start()
    made.wait_until_healthy()
    yield made
    made.stop()


@needs_runtime
@sandbox_test
def test_a_started_sandbox_becomes_healthy_and_reports_its_services(sandbox):
    health = sandbox.health()
    assert health is not None
    assert health.version
    assert len(health.available) >= 60
    assert sandbox.is_running()


@needs_runtime
@sandbox_test
def test_resetting_a_running_sandbox_succeeds(sandbox):
    sandbox.reset()
    assert sandbox.health() is not None


@needs_runtime
@sandbox_test
def test_starting_an_already_running_sandbox_does_nothing(sandbox):
    sandbox.start()
    assert sandbox.is_running()


@needs_runtime
@sandbox_test
def test_stopping_leaves_nothing_behind():
    made = Sandbox(name=f"backsight-test-stop-{os.getpid()}", port=15400 + os.getpid() % 300)
    made.start()
    made.wait_until_healthy()
    made.stop()
    assert made.is_present() is False
    assert made.health(timeout=0.5) is None


@needs_runtime
@sandbox_test
def test_the_image_is_present_after_a_start(sandbox):
    assert sandbox.has_image()
