"""What the palette matches, and in what order.

The prefixes are the whole surface area: nothing lives only in a menu,
so this is how everything is reached.

| Prefix | What it searches |
|---|---|
| none | files |
| `@` | resources, data sources, variables, outputs |
| `:` | a line number |
| `#` | provider and catalog documentation |
| `>` | commands |
| `!` | problems and findings — the fastest way to what is blocking you |

**It opens with suggestions and never an empty prompt.** A blank palette is a
wall for anyone who touches Terraform monthly, and that single list is what
keeps both the daily user and the occasional author served — FR-APP-11.

This module ranks; it fetches nothing. Deciding what a file, a resource or a
command *is* belongs to the layers that already know.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Kind(Enum):
    """What a query is asking for. The prefix decides, never a guess."""

    FILE = ""
    RESOURCE = "@"
    LINE = ":"
    DOCUMENTATION = "#"
    COMMAND = ">"
    # The Problems drawer tab was folded into Changes on the reasoning that the
    # plan panel and the verdict line already answer it. This is the keyboard
    # answer, and without it the capability has no keyboard route at all.
    PROBLEM = "!"


PREFIXES = {kind.value: kind for kind in Kind if kind.value}

# What each group is called on screen. The design puts matches first and
# suggestions below them, always.
HEADINGS = {
    Kind.FILE: "Files",
    Kind.RESOURCE: "Resources",
    Kind.LINE: "Go to line",
    Kind.DOCUMENTATION: "Documentation",
    Kind.COMMAND: "Matches",
    Kind.PROBLEM: "Problems",
}

SUGGESTED = "Suggested"


@dataclass(frozen=True)
class Entry:
    """One thing the palette can offer."""

    label: str
    kind: Kind
    action: str | None = None
    detail: str = ""
    # Ranked above an equally good match. What a resource address gives you
    # over a filename: the parser already knows it.
    weight: int = 0


@dataclass(frozen=True)
class Query:
    """A typed query, split into what it searches and what it searches for."""

    kind: Kind
    term: str
    raw: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.term


@dataclass(frozen=True)
class Results:
    """What to draw: the matches, then the suggestions, each under a heading."""

    query: Query
    matches: list[Entry] = field(default_factory=list)
    suggestions: list[Entry] = field(default_factory=list)

    @property
    def heading(self) -> str:
        return HEADINGS[self.query.kind]

    @property
    def is_empty(self) -> bool:
        """True only when there is nothing at all to show, which never happens
        while suggestions exist — that is the point of them."""
        return not self.matches and not self.suggestions


def parse(raw: str) -> Query:
    """Reads the prefix off a query. Without one it is a file search."""
    text = raw.lstrip()
    if text and text[0] in PREFIXES:
        return Query(kind=PREFIXES[text[0]], term=text[1:].strip(), raw=raw)
    return Query(kind=Kind.FILE, term=text.strip(), raw=raw)


def score(label: str, term: str) -> int | None:
    """How well a label matches, or None when it does not.

    Three tiers, best first: the label starts with the term, a word in it
    starts with the term, or the characters appear in order. Subsequence
    matching is last because it matches almost everything.

    An empty term matches everything equally, which is why the caller decides
    whether to ask at all.
    """
    if not term:
        return 0
    haystack = label.lower()
    needle = term.lower()
    if haystack.startswith(needle):
        return 300 - len(label)
    if any(word.startswith(needle) for word in _words(haystack)):
        return 200 - len(label)
    if _in_order(haystack, needle):
        return 100 - len(label)
    return None


def rank(entries: list[Entry], query: Query) -> list[Entry]:
    """Every entry of the right kind that matches, best first."""
    scored: list[tuple[int, int, str, Entry]] = []
    for index, entry in enumerate(entries):
        if entry.kind is not query.kind:
            continue
        found = score(entry.label, query.term)
        if found is None:
            continue
        # Index last, so an equal score keeps the order it was given in rather
        # than an arbitrary one.
        scored.append((-(found + entry.weight), index, entry.label, entry))
    scored.sort(key=lambda row: (row[0], row[1]))
    return [entry for _, _, _, entry in scored]


def results(entries: list[Entry], suggestions: list[Entry], raw: str) -> Results:
    """Everything the palette shows for one query.

    Suggestions stay below the matches and are never removed. An empty query
    shows suggestions alone, which is what stops the palette being a wall.
    """
    query = parse(raw)
    if query.kind is Kind.LINE:
        return Results(query=query, matches=_line(query), suggestions=[])
    # An empty query offers suggestions and nothing else. Listing every command
    # in the application would be the wall the suggestions exist to avoid.
    matched = rank(entries, query) if not query.is_empty else []
    shown = [entry for entry in suggestions if entry not in matched]
    return Results(query=query, matches=matched, suggestions=shown)


def _line(query: Query) -> list[Entry]:
    """A line number is not a search — it either is one or it is not."""
    if not query.term.isdigit() or int(query.term) < 1:
        return []
    return [Entry(label=f"Line {int(query.term)}", kind=Kind.LINE, action="goto-line")]


def _words(text: str) -> list[str]:
    for separator in ("_", "-", ".", "/", ":"):
        text = text.replace(separator, " ")
    return text.split()


def _in_order(haystack: str, needle: str) -> bool:
    position = 0
    for character in needle:
        position = haystack.find(character, position)
        if position < 0:
            return False
        position += 1
    return True
