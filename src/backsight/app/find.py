"""Find and replace, on GtkSourceView's own search.

The find row: in file, regex, case and whole word, incremental, find in
selection, replace and replace all. All of it is `GtkSource.SearchContext`; this
is the shape the interface talks to it through.

Replace-all reports how many it changed **before** doing it, because "replace
all" with no number is a decision made blind.
"""

from __future__ import annotations

from dataclasses import dataclass

import gi

gi.require_version("GtkSource", "5")

from gi.repository import GtkSource


@dataclass(frozen=True)
class Query:
    """What is being looked for, and how."""

    text: str
    regex: bool = False
    case_sensitive: bool = False
    whole_word: bool = False
    wrap: bool = True


class Search:
    """One buffer's search, kept so the highlight follows the typing."""

    def __init__(self, buffer: GtkSource.Buffer) -> None:
        self._settings = GtkSource.SearchSettings()
        self._context = GtkSource.SearchContext(buffer=buffer, settings=self._settings)
        self._buffer = buffer
        self._watchers: list = []
        # The scan runs in the background and `count` is -1 until it finishes,
        # so a caller that reads the count once always reads "still counting".
        self._context.connect("notify::occurrences-count", lambda *_: self._changed())

    def look_for(self, query: Query) -> None:
        self._settings.set_search_text(query.text or None)
        self._settings.set_regex_enabled(query.regex)
        self._settings.set_case_sensitive(query.case_sensitive)
        self._settings.set_at_word_boundaries(query.whole_word)
        self._settings.set_wrap_around(query.wrap)

    @property
    def count(self) -> int:
        """How many matches. `-1` while the scan is still running."""
        return self._context.get_occurrences_count()

    def next(self) -> bool:
        return self._move(forward=True)

    def previous(self) -> bool:
        return self._move(forward=False)

    def replace_all(self, replacement: str) -> int:
        """Returns how many were changed, which the interface must show."""
        return self._context.replace_all(replacement, -1)

    def clear(self) -> None:
        self._settings.set_search_text(None)

    def on_count(self, watcher) -> None:
        """Called whenever the running scan revises how many it has found."""
        self._watchers.append(watcher)

    def _changed(self) -> None:
        for watcher in self._watchers:
            watcher(self.count)

    def _move(self, *, forward: bool) -> bool:
        where = self._buffer.get_iter_at_mark(self._buffer.get_insert())
        if forward:
            found, start, end, _wrapped = self._context.forward(where)
        else:
            found, start, end, _wrapped = self._context.backward(where)
        if found:
            self._buffer.select_range(start, end)
        return found
