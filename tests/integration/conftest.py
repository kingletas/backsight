"""What every integration test shares: an emulator, a workspace, and a way back.

**The application is the system under test.** Nothing here calls the engine
directly to make something happen — every command goes through the function the
application calls, so a defect in argument construction, working directory,
environment, process lifecycle or output parsing fails here rather than being
stepped over.

The direct CLI and the emulator's own API appear only as **verification**: after
the application has done something, these ask the emulator whether it actually
happened. That is the half a green exit code cannot tell you.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "infra-test" / "terraform"
COMPOSE = ROOT / "infra-test" / "docker-compose.yml"

# Not 4566, MiniStack's default: an emulator already there belongs to whoever
# started it, and a suite that resets somebody else's emulator between
# cases is a suite that deletes their work.
PORT = int(os.environ.get("MINISTACK_PORT", "14566"))
ENDPOINT = f"http://127.0.0.1:{PORT}"

# The engine the application invokes. Pinned by the environment rather than
# discovered, so a run says which one it was about.
ENGINE = os.environ.get("BACKSIGHT_ENGINE", "tofu")


# **One provider download for the whole run.** Every case works in its own copy,
# so without this each one fetched the AWS provider again — the suite spent
# eighteen minutes and almost all of it was the same download. The cache is the
# engine's own mechanism and it is what CI would use anyway.
def _cache_directory() -> Path:
    """Absolute, always: every engine run works in its own copy, so a relative
    path would name a different directory inside each one and share nothing."""
    named = os.environ.get("TF_PLUGIN_CACHE_DIR")
    found = Path(named) if named else ROOT / "local.d" / "plugin-cache"
    return found if found.is_absolute() else ROOT / found


CACHE = _cache_directory()

# The five the application's own fixtures exercise, and no more. Every extra
# service is start-up time bought for coverage nobody asked for.
WANTED = frozenset({"s3", "sqs", "dynamodb", "sts", "iam"})

# The emulator takes any credentials. These are the ones its own documentation
# uses and they are not a secret in any sense.
CREDENTIALS = {
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_REGION": "us-east-1",
}


def health() -> dict | None:
    """What the emulator says about itself, or nothing when it is not there."""
    try:
        # The URL is built from a loopback constant in this file, so there is
        # no scheme here for a caller to choose.
        with urllib.request.urlopen(f"{ENDPOINT}/_ministack/health", timeout=3) as answer:  # noqa: S310
            return json.load(answer)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def available() -> frozenset[str]:
    said = health()
    if said is None:
        return frozenset()
    services = said.get("services") or {}
    return frozenset(name for name, state in services.items() if state == "available")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: drives the emulator in infra-test/")


HERE = Path(__file__).parent


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Every test **in this directory** is an integration test, said once here.

    Marking each one by hand is a mark somebody forgets, and a forgotten mark is
    a test that runs in the unit suite and fails on a machine with no Docker.

    The path check is not decoration: a `conftest.py` in a subdirectory is
    handed **every** item in the session, so without it this marked the whole
    suite as integration and `make test` collected nothing at all.
    """
    for item in items:
        if HERE in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def emulator() -> dict:
    """The running emulator, or a skip that says exactly what to run.

    It does **not** start one. Starting a container from inside a test means the
    suite owns a lifetime it cannot guarantee to end — `infra-test/scripts/test`
    owns it instead, and cleans up on every ending including a Ctrl-C.
    """
    said = health()
    if said is None:
        pytest.skip(
            f"no emulator on {ENDPOINT}. Run `infra-test/scripts/up`, or "
            "`infra-test/scripts/test` to do the whole thing."
        )
    missing = WANTED - available()
    if missing:
        pytest.skip(f"the emulator is running without {', '.join(sorted(missing))}")
    return said


@pytest.fixture(scope="session", autouse=True)
def _one_provider_download() -> None:
    """Points every engine run at one cache, for the whole session.

    Set on `os.environ` rather than passed, because the application's own
    invocations inherit the environment and do not take one — which is the
    point: they are the thing under test and they are not changed to be tested.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    os.environ["TF_PLUGIN_CACHE_DIR"] = str(CACHE)
    for name, value in CREDENTIALS.items():
        os.environ.setdefault(name, value)


@pytest.fixture(scope="session")
def engine(emulator: dict) -> str:
    """The engine binary, checked once so a missing one skips rather than fails
    fifteen times with a file-not-found."""
    if shutil.which(ENGINE) is None:
        pytest.skip(f"{ENGINE} is not on PATH")
    return ENGINE


def reset() -> None:
    """Empties the emulator, which is what belongs between cases.

    A restart costs several seconds and this costs one call — and a case that
    passes because of what the last one left behind is worse than a slow suite.
    """
    request = urllib.request.Request(f"{ENDPOINT}/_ministack/reset", method="POST")  # noqa: S310
    try:
        urllib.request.urlopen(request, timeout=10).close()  # noqa: S310
    except (urllib.error.URLError, TimeoutError, OSError):
        # Reported rather than raised: a reset that did not happen makes the
        # next test fail on its own terms, which is more informative than this
        # one failing in teardown.
        pass


@dataclass
class Workspace:
    """One isolated copy of a fixture, pointed at the emulator.

    A copy, always. The application's own sandbox mechanism writes a provider
    override into a scratch directory rather than editing the workspace, and
    using it here is what proves that mechanism as well as using it.
    """

    path: Path
    endpoint: str
    engine: str

    @property
    def environment(self) -> dict[str, str]:
        return {**os.environ, **CREDENTIALS, "TF_PLUGIN_CACHE_DIR": str(CACHE)}

    def run(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess:
        """The engine, directly. **For fixture setup and verification only** —
        never to make the thing under test happen."""
        return subprocess.run(
            [self.engine, *arguments],
            cwd=self.path,
            capture_output=True,
            text=True,
            env=self.environment,
            timeout=600,
            check=check,
        )


def _override(where: Path, endpoint: str) -> None:
    """Points the copy at the emulator, using the application's own override.

    `sandbox.override` is what the application writes when it runs a
    convergence check, so this exercises it rather than inventing a second way
    to redirect a provider.
    """
    from backsight.engine.sandbox.override import override_hcl

    (where / "backsight_sandbox_override.tf").write_text(
        override_hcl(endpoint, sorted(WANTED)), encoding="utf-8"
    )


@pytest.fixture
def workspace(request: pytest.FixtureRequest, engine: str, tmp_path: Path) -> Iterator[Workspace]:
    """An isolated copy of one fixture, cleaned up whatever happens.

    Which fixture comes from `@pytest.mark.fixture_name("base")`; `base` is the
    default because most cases want it.
    """
    marker = request.node.get_closest_marker("fixture_name")
    name = marker.args[0] if marker else "base"
    source = FIXTURES / name
    assert source.is_dir(), f"no such fixture: infra-test/terraform/{name}"

    where = tmp_path / name
    shutil.copytree(source, where)
    if name not in ("outputs", "unreachable"):
        _override(where, ENDPOINT)

    made = Workspace(path=where, endpoint=ENDPOINT, engine=engine)
    try:
        yield made
    finally:
        # **On every ending**: success, an assertion, an engine failure, a
        # timeout, a Ctrl-C. A case that leaves objects behind is one whose
        # neighbours pass or fail because of it.
        _destroy_quietly(made)
        reset()


def _destroy_quietly(made: Workspace) -> None:
    """Takes down whatever a case created, without turning teardown into a
    second failure to read."""
    if not (made.path / "terraform.tfstate").exists():
        return
    try:
        made.run("destroy", "-auto-approve", "-input=false", "-no-color", check=False)
    except (subprocess.TimeoutExpired, OSError):
        return


@pytest.fixture
def named() -> str:
    """A name nothing else in the run will use, so two cases cannot collide."""
    return f"bs-{uuid.uuid4().hex[:10]}"
