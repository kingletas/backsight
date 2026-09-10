"""Whether a newer provider version exists, and saying when we do not know.

The registry response is a real capture — the ordering it returns is the
registry's convention rather than a promise, and reading the newest by comparing
is the difference between an answer and a guess.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from backsight.engine.schema.latest import (
    NotASource,
    Versions,
    _fetch,
    newest_in,
)

FIXTURE = (
    Path(__file__).resolve().parents[1].parent
    / "fixtures"
    / "registry"
    / "opentofu-local-versions.json"
)


def registry_answer() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def a_check(answer=None, fails=None) -> Versions:
    def fetch(_source: str) -> dict:
        if fails is not None:
            raise fails
        return answer if answer is not None else registry_answer()

    return Versions(fetch=fetch, now=lambda: 0.0)


def test_it_reads_the_newest_version_out_of_a_real_response():
    assert newest_in(registry_answer()) == "2.9.0"


def test_the_newest_is_compared_rather_than_taken_from_the_top():
    """Newest-first is a convention, not a promise, and a wrong answer here
    would be a confident one."""
    shuffled = {"versions": [{"version": "2.1.0"}, {"version": "2.10.0"}, {"version": "2.9.0"}]}
    assert newest_in(shuffled) == "2.10.0"


def test_a_behind_provider_says_what_is_available():
    found = a_check().check("local", installed="2.5.1", source="opentofu/local")
    assert found.is_behind
    assert found.summary == "2.9.0 available"


def test_a_current_provider_says_nothing_at_all():
    """A row that says "up to date" on every provider is a column of noise."""
    found = a_check().check("local", installed="2.9.0", source="opentofu/local")
    assert not found.is_behind
    assert found.summary == ""


def test_a_provider_ahead_of_the_registry_is_not_behind():
    found = a_check().check("local", installed="3.0.0", source="opentofu/local")
    assert not found.is_behind


def test_a_registry_that_cannot_be_reached_says_it_does_not_know():
    """On a plane or behind a proxy, "no newer version" would be a claim."""
    found = a_check(fails=urllib.error.URLError("no route")).check(
        "local", installed="2.5.1", source="opentofu/local"
    )
    assert not found.is_known
    assert not found.is_behind
    assert found.why_not == "the registry could not be reached"
    assert found.summary == ""


def test_a_provider_the_registry_has_never_heard_of_is_a_silence():
    found = a_check(
        fails=urllib.error.HTTPError("u", 404, "nope", {}, None)  # type: ignore[arg-type]
    ).check("private", installed="1.0.0", source="us/private")
    assert found.why_not == "not on this registry"
    assert found.summary == ""


def test_a_bare_name_is_not_asked_about():
    """Guessing `hashicorp/` would be inventing the subject of the answer."""
    found = a_check().check("aws", installed="5.0.0")
    assert not found.asked
    assert found.why_not == "no registry namespace"


def test_an_answer_is_kept_rather_than_asked_for_twice():
    asked = []

    def fetch(source: str) -> dict:
        asked.append(source)
        return registry_answer()

    versions = Versions(fetch=fetch, now=lambda: 0.0)
    versions.check("local", "2.5.1", "opentofu/local")
    versions.check("local", "2.5.1", "opentofu/local")
    assert asked == ["opentofu/local"]


def test_a_kept_answer_expires():
    asked = []
    clock = {"now": 0.0}

    def fetch(source: str) -> dict:
        asked.append(source)
        return registry_answer()

    versions = Versions(fetch=fetch, now=lambda: clock["now"])
    versions.check("local", "2.5.1", "opentofu/local")
    clock["now"] = 10**9
    versions.check("local", "2.5.1", "opentofu/local")
    assert len(asked) == 2


def test_a_source_that_would_change_which_server_is_asked_is_refused():
    """It comes out of a lock file in somebody's repository and goes into a URL,
    so it is treated as attacker-controlled."""
    for said in ("../../evil", "evil.com/x/../..", "a//b", "a/b/c", "", "a b/c"):
        with pytest.raises(NotASource):
            _fetch(said)


def test_a_refused_source_reads_as_not_knowing_rather_than_a_crash():
    found = Versions().check("x", installed="1.0.0", source="../../evil")
    assert not found.is_known
    assert found.why_not == "that provider source is not one this can ask about"
