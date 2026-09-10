"""Snippets insert valid HCL; the clipboard ring keeps what was copied."""

from __future__ import annotations

from backsight.engine.hcl.navigation import blocks
from backsight.engine.presentation.clipboard import History
from backsight.engine.presentation.snippets import SNIPPETS, body_of


def test_every_snippet_parses_as_hcl():
    """A snippet that does not parse teaches the wrong thing on the way in."""
    for snippet in SNIPPETS:
        found = blocks(snippet.body.encode("utf-8"))
        assert found, f"{snippet.name} does not parse"


def test_every_snippet_has_a_name_the_menu_uses():
    for snippet in SNIPPETS:
        assert snippet.name.startswith("snippet-")
        assert body_of(snippet.name) == snippet.body


def test_a_name_nothing_declares_gets_nothing():
    assert body_of("snippet-nonsense") is None


def test_snippets_use_two_space_indentation():
    """What `tofu fmt` produces. Arriving needing reformatting is a bad start."""
    for snippet in SNIPPETS:
        for line in snippet.body.splitlines():
            if line.startswith(" "):
                assert line.startswith("  ")
                assert not line.startswith("   ")


def test_the_newest_copy_comes_first():
    history = History()
    history.remember("one")
    history.remember("two")
    assert history.items == ["two", "one"]


def test_copying_the_same_thing_again_moves_it_rather_than_repeating_it():
    history = History()
    history.remember("one")
    history.remember("two")
    history.remember("one")
    assert history.items == ["one", "two"]


def test_the_ring_is_bounded_and_the_oldest_goes_first():
    history = History(depth=3)
    for text in ("a", "b", "c", "d"):
        history.remember(text)
    assert history.items == ["d", "c", "b"]


def test_copying_nothing_is_not_a_copy():
    history = History()
    history.remember("")
    assert history.items == []
