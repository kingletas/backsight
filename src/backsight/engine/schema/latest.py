"""Whether a newer version of a provider exists, and saying when we do not know.

Versions are displayed already; knowing one is out of date needs somebody to ask
a registry, and that is the only thing in this application that reaches the
network. So three rules hold it:

**It is asked for, never assumed.** Off unless somebody turns it on. An editor
that phones a registry the first time it opens a workspace is doing something
the person did not ask for with a workspace they may not want announced.

**Not knowing is an answer.** On a plane, behind a proxy, or against a private
registry, the check cannot run — and "no newer version" would be a claim. It
says it does not know, and the version on screen is unchanged either way.

**An answer is kept.** A registry does not publish a new provider between two
keystrokes, so a cached answer with its age on it beats a request per redraw.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field

from backsight.engine.schema.resolution import parse_version

# The public registry. A private one answers the same shape at its own host.
REGISTRY = "https://registry.opentofu.org/v1/providers"

# Long enough that a session asks once, short enough to be worth asking.
KEEP_SECONDS = 6 * 60 * 60

# Short: this is a convenience, and a slow registry must never be something a
# person waits behind.
TIMEOUT = 4.0


@dataclass(frozen=True)
class Newer:
    """What is known about one provider's versions."""

    name: str
    installed: str
    newest: str = ""
    asked: bool = False
    why_not: str = ""

    @property
    def is_known(self) -> bool:
        return self.asked and not self.why_not and bool(self.newest)

    @property
    def is_behind(self) -> bool:
        """Only ever true when an answer was actually received."""
        if not self.is_known or not self.installed:
            return False
        return parse_version(self.newest) > parse_version(self.installed)

    @property
    def summary(self) -> str:
        """One phrase for beside the version, and nothing when there is none."""
        if self.why_not:
            return ""
        if not self.asked:
            return ""
        return f"{self.newest} available" if self.is_behind else ""


def newest_in(document: dict) -> str:
    """The highest version in a registry response.

    Read by comparing rather than by taking the first: the ordering is the
    registry's convention and not a promise, and a wrong answer here would be a
    confident one.
    """
    versions = [
        str(entry.get("version", ""))
        for entry in document.get("versions") or []
        if entry.get("version")
    ]
    if not versions:
        return ""
    return max(versions, key=parse_version)


# A provider source is `namespace/type`, and both halves are a restricted set.
# This value comes out of a lock file in somebody's repository, so it is treated
# as attacker-controlled: it is put into a URL, and a `//host` or a `..` in it
# would decide which server this talks to.
SOURCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class NotASource(ValueError):
    """A provider source that will not be put into a URL."""


def _fetch(source: str, *, timeout: float = TIMEOUT) -> dict:
    """One registry request. Every failure is the same kind of answer."""
    if not SOURCE.match(source):
        raise NotASource(source)
    url = f"{REGISTRY}/{source}/versions"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})  # noqa: S310
    # https by construction: the scheme is in REGISTRY and the rest is matched
    # against SOURCE above, so no caller can change where this goes.
    with urllib.request.urlopen(request, timeout=timeout) as answer:  # noqa: S310
        return json.loads(answer.read().decode("utf-8"))


@dataclass
class Versions:
    """What has been asked, and what came back. One per session."""

    fetch: Callable[[str], dict] = _fetch
    now: Callable[[], float] = time.monotonic
    _answers: dict[str, tuple[float, str]] = field(default_factory=dict)

    def check(self, name: str, installed: str, source: str | None = None) -> Newer:
        """Asks about one provider, or answers from what is already known."""
        where = source or name
        if "/" not in where:
            # A bare name has no namespace, so there is nothing to ask about.
            # Guessing `hashicorp/` would be inventing the answer's subject.
            return Newer(name=name, installed=installed, why_not="no registry namespace")

        kept = self._answers.get(where)
        if kept is not None and self.now() - kept[0] < KEEP_SECONDS:
            return Newer(name=name, installed=installed, newest=kept[1], asked=True)

        try:
            document = self.fetch(where)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as refused:
            return Newer(name=name, installed=installed, why_not=_why(refused))

        newest = newest_in(document)
        if not newest:
            return Newer(name=name, installed=installed, why_not="the registry listed no versions")
        self._answers[where] = (self.now(), newest)
        return Newer(name=name, installed=installed, newest=newest, asked=True)


def _why(refused: Exception) -> str:
    """Why the check could not run, in a phrase rather than a traceback."""
    if isinstance(refused, urllib.error.HTTPError) and refused.code == 404:
        return "not on this registry"
    if isinstance(refused, NotASource):
        return "that provider source is not one this can ask about"
    if isinstance(refused, TimeoutError | urllib.error.URLError):
        return "the registry could not be reached"
    return "the registry's answer could not be read"
