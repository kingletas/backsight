"""The parts of a stored body you fill in, and where they land.

The syntax is `${1}` and `${1:default}`, which is what every other editor uses
and therefore what anybody writing an entry already knows.

**A digit immediately after `${` is what makes it a placeholder.** HCL's own
interpolation is also `${...}` — `"${var.environment}-logs"` — and an HCL
identifier cannot begin with a digit, so the two are unambiguous by
construction and a body can be plain Terraform with no escaping anywhere.

The toolkit has its own snippet engine and it cannot be used: its parser eats
the opening brace of every HCL interpolation, with no escape that round-trips.
See `docs/findings/014`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# `${` then digits, then either `}` or `:default}`. The default may contain
# anything but a closing brace, which keeps a nested interpolation out of it —
# a default that itself needs `${}` is a body, not a default.
PLACEHOLDER = re.compile(r"\$\{(\d+)(?::([^}]*))?\}")

# Where the caret lands when the last stop is left. `${0}` by convention.
LAST = 0


@dataclass(frozen=True)
class Stop:
    """One place to type, and what is there until somebody does."""

    number: int
    start: int
    end: int
    default: str

    @property
    def is_the_end(self) -> bool:
        """`${0}` is where the caret rests, never a field to fill in."""
        return self.number == LAST

    @property
    def length(self) -> int:
        return self.end - self.start


@dataclass(frozen=True)
class Filled:
    """A body with its placeholders resolved, and where each one ended up."""

    text: str
    stops: tuple[Stop, ...] = ()

    @property
    def has_stops(self) -> bool:
        return any(not stop.is_the_end for stop in self.stops)

    @property
    def first(self) -> Stop | None:
        return self.stops[0] if self.stops else None


def has_placeholders(body: str) -> bool:
    return bool(PLACEHOLDER.search(body))


def resolve(body: str) -> Filled:
    """Replaces every placeholder with its default and records the offsets.

    Ordered by number, then by where they appear, so tabbing follows the order
    whoever wrote the entry intended rather than the order the text happens to
    be in. `${0}` always comes last, because it is where you end up.
    """
    found: list[tuple[int, int, int, str]] = []
    pieces: list[str] = []
    at = 0
    written = 0
    for match in PLACEHOLDER.finditer(body):
        pieces.append(body[at : match.start()])
        written += match.start() - at
        default = match.group(2) or ""
        found.append((int(match.group(1)), written, written + len(default), default))
        pieces.append(default)
        written += len(default)
        at = match.end()
    pieces.append(body[at:])

    stops = tuple(
        Stop(number=number, start=start, end=end, default=default)
        for number, start, end, default in sorted(found, key=_ordering)
    )
    return Filled(text="".join(pieces), stops=stops)


def _ordering(found: tuple[int, int, int, str]) -> tuple[int, int, int]:
    """`${1}` before `${2}`, and `${0}` after everything."""
    number, start, _end, _default = found
    return (1 if number == LAST else 0, number, start)


def strip(body: str) -> str:
    """The body with every placeholder replaced by its default.

    What a preview shows, and what goes in when the person asked for the text
    rather than for something to fill in.
    """
    return resolve(body).text


def numbers_in(body: str) -> list[int]:
    return [int(match.group(1)) for match in PLACEHOLDER.finditer(body)]
