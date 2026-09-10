"""Find and replace on a real buffer."""

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("GtkSource", "5")

from gi.repository import GLib, GtkSource  # noqa: E402

from backsight.app.find import Query, Search  # noqa: E402

FILE = 'resource "a" "one" {\n  input = "ONE"\n}\n\nresource "a" "two" {\n  input = "one"\n}\n'


def until_counted(search, seconds: float = 5.0) -> None:
    """Waits for the scan to report, rather than for a fixed length of time.

    `GtkSource.SearchContext` counts in the background and returns -1 until it
    is done. A fixed pause is right until the machine is busy, and then it is a
    test that fails for a reason that has nothing to do with the code.
    """
    import time  # noqa: PLC0415

    context = GLib.MainContext.default()
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        if search.count >= 0:
            return
        if not context.iteration(False):
            time.sleep(0.005)


def search_for(query: Query, text: str = FILE):
    buffer = GtkSource.Buffer()
    buffer.set_text(text)
    search = Search(buffer)
    search.look_for(query)
    until_counted(search)
    return buffer, search


def test_a_plain_search_finds_every_case_by_default():
    _buffer, search = search_for(Query(text="one"))
    assert search.count == 3


def test_case_sensitivity_narrows_it():
    _buffer, search = search_for(Query(text="one", case_sensitive=True))
    assert search.count == 2


def test_whole_word_narrows_it_further():
    _buffer, search = search_for(Query(text="resource", whole_word=True))
    assert search.count == 2


def test_a_regular_expression_is_honoured():
    _buffer, search = search_for(Query(text=r'"[a-z]+"\s*\{', regex=True))
    assert search.count == 2


def test_moving_forward_selects_the_match():
    buffer, search = search_for(Query(text="input"))
    assert search.next() is True
    bounds = buffer.get_selection_bounds()
    assert bounds
    start, end = bounds
    assert buffer.get_text(start, end, True) == "input"


def test_searching_for_nothing_finds_nothing():
    _buffer, search = search_for(Query(text="not in this file"))
    assert search.count == 0
    assert search.next() is False


def test_replace_all_says_how_many_it_changed():
    """ "Replace all" with no number is a decision made blind."""
    buffer, search = search_for(Query(text="one", case_sensitive=True))
    changed = search.replace_all("uno")
    assert changed == 2
    text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
    assert '"ONE"' in text, "the case-sensitive search should have left this alone"
    assert text.count("uno") == 2


def test_clearing_the_search_removes_the_highlight():
    _buffer, search = search_for(Query(text="one"))
    search.clear()
    until_counted(search)
    assert search.count == 0
