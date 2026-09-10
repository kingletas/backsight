"""Finding a container runtime, and saying so plainly when there is not one.

FR-SIM-10. Convergence testing is one feature of several, so its absence
degrades the product rather than breaking it — but it has to say what is missing
and what to do, rather than failing somewhere deep with a file-not-found.

Podman is preferred over Docker. §9.5: Snap and Flatpak confinement both
restrict access to the Docker socket, and rootless Podman is the one that
survives being packaged.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass

# In order of preference. Podman first for the packaging reason above.
KNOWN = ("podman", "docker")

MISSING = (
    "Convergence testing needs a container runtime and neither Podman nor "
    "Docker is installed. Everything else works without one.\n"
    "    sudo apt install podman"
)


@dataclass(frozen=True)
class Runtime:
    """A container runtime that is actually on this machine."""

    name: str
    binary: str

    @property
    def is_rootless_capable(self) -> bool:
        """Podman runs rootless, which is what confined packaging needs."""
        return self.name == "podman"


class NoRuntime(Exception):
    """Neither runtime is installed. Carries the message a person should read."""

    def __init__(self) -> None:
        super().__init__(MISSING)


def detect(candidates: tuple[str, ...] = KNOWN) -> Runtime | None:
    """The runtime to use, or nothing. Never raises: absence is an ordinary state."""
    for name in candidates:
        found = shutil.which(name)
        if found:
            return Runtime(name=name, binary=found)
    return None


def require(candidates: tuple[str, ...] = KNOWN) -> Runtime:
    """The runtime, or a refusal that says what to install."""
    found = detect(candidates)
    if found is None:
        raise NoRuntime
    return found
