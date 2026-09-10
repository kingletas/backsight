"""Managing the emulator container, so nobody has to type a container command.

FR-SIM-01. Pull, start, health-check, reset between runs, stop.

The health endpoint is also the coverage source: it reports which services this
build of the emulator actually has, and that is what FR-SIM-04 counts against.
Asking the running container beats a table in this repository that goes stale
the first time somebody upgrades it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from backsight.engine.runner import process
from backsight.engine.sandbox.runtime import Runtime, require

IMAGE = "ministackorg/ministack"
VERSION = "1.5.8"
CONTAINER_PORT = 4566

# Not 4566. A developer machine may already be running something on the usual
# port, and taking it would be rude and confusing.
DEFAULT_PORT = 14566
DEFAULT_NAME = "backsight-sandbox"

# Two windows open on two workspaces would share this name and this port, and the
# second to close would remove the first's container out from under it. Not yet
# decided: one sandbox shared between workspaces, or one each. Until it is, a
# caller that wants its own passes its own name and port.

HEALTH_PATH = "/_ministack/health"
RESET_PATH = "/_ministack/reset"

START_TIMEOUT = 120.0
PULL_TIMEOUT = 900.0


@dataclass(frozen=True)
class Health:
    """What the emulator says about itself."""

    version: str
    edition: str
    services: dict[str, str] = field(default_factory=dict)

    @property
    def available(self) -> frozenset[str]:
        return frozenset(name for name, state in self.services.items() if state == "available")


class SandboxError(Exception):
    """Something about the container went wrong, said in words."""


@dataclass
class Sandbox:
    """One emulator container, and everything done to it."""

    runtime: Runtime = field(default_factory=require)
    image: str = IMAGE
    version: str = VERSION
    port: int = DEFAULT_PORT
    name: str = DEFAULT_NAME

    @property
    def reference(self) -> str:
        return f"{self.image}:{self.version}"

    @property
    def endpoint(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def is_present(self) -> bool:
        """Whether a container of ours exists, running or not."""
        result = self._run(
            ["ps", "-a", "--filter", f"name=^{self.name}$", "--format", "{{.Names}}"]
        )
        return self.name in result.output.split()

    def is_running(self) -> bool:
        result = self._run(["ps", "--filter", f"name=^{self.name}$", "--format", "{{.Names}}"])
        return self.name in result.output.split()

    def has_image(self) -> bool:
        result = self._run(["image", "inspect", self.reference], check=False)
        return result.ok

    def pull(self) -> None:
        result = self._run(["pull", self.reference], timeout=PULL_TIMEOUT, check=False)
        if not result.ok:
            raise SandboxError(f"Could not fetch {self.reference}.\n{result.output.strip()}")

    def start(self) -> None:
        """Starts the container, fetching the image first if it is not here."""
        if self.is_running():
            return
        if not self.has_image():
            self.pull()
        if self.is_present():
            # A stopped container of ours from a previous session. Removing it is
            # cheaper than reasoning about what state it was left in.
            self.remove()
        result = self._run(
            [
                "run",
                "-d",
                "--name",
                self.name,
                "-p",
                f"127.0.0.1:{self.port}:{CONTAINER_PORT}",
                self.reference,
            ],
            check=False,
        )
        if not result.ok:
            raise SandboxError(f"Could not start the sandbox.\n{result.output.strip()}")

    def stop(self) -> None:
        if self.is_present():
            self._run(["rm", "-f", self.name], check=False)

    def remove(self) -> None:
        self._run(["rm", "-f", self.name], check=False)

    def health(self, timeout: float = 2.0) -> Health | None:
        """What the emulator reports, or nothing when it is not answering."""
        try:
            with urllib.request.urlopen(  # noqa: S310
                f"{self.endpoint}{HEALTH_PATH}", timeout=timeout
            ) as response:
                document: dict[str, Any] = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return None
        return Health(
            version=str(document.get("version", "")),
            edition=str(document.get("edition", "")),
            services=dict(document.get("services") or {}),
        )

    def wait_until_healthy(self, timeout: float = START_TIMEOUT) -> Health:
        """Waits for the condition rather than for a duration."""
        import time  # noqa: PLC0415

        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            found = self.health()
            if found is not None:
                return found
            time.sleep(0.25)
        raise SandboxError(
            f"The sandbox did not become healthy within {timeout:.0f}s. "
            f"Check `{self.runtime.name} logs {self.name}`."
        )

    def reset(self) -> None:
        """Wipes every service back to empty, between runs.

        Cheaper than restarting the container, and FR-SIM-01 asks for it so one
        run cannot see what a previous run left behind.
        """
        request = urllib.request.Request(f"{self.endpoint}{RESET_PATH}", method="POST")  # noqa: S310
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                body = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as error:
            raise SandboxError(f"Could not reset the sandbox: {error}") from error
        if body.get("reset") != "ok":
            raise SandboxError(f"The sandbox refused to reset: {body}")

    def _run(self, arguments: list[str], *, timeout: float = 60.0, check: bool = True):
        result = process.start([self.runtime.binary, *arguments], timeout=timeout).wait(
            timeout + 10
        )
        if check and not result.ok:
            raise SandboxError(
                f"{self.runtime.name} {' '.join(arguments[:2])} failed.\n{result.output.strip()}"
            )
        return result
