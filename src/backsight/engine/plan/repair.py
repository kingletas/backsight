"""Saying what a diagnostic means, and fixing it where the fix is not a guess.

The engine writes for somebody who already knows the tool. "Invalid quoted type
constraints" names the rule that was broken rather than the mistake that was
made, and the paragraph under it explains the history of a version that shipped
in 2017. Both are accurate and neither is what a person needs at the moment the
plan stops.

So each diagnostic gets a title written for the reader and one sentence of
explanation. **The engine's own text is never replaced by this** — it stays
verbatim behind `Show the original`, because a translation nobody can check against
the original is just a different opacity.

A few of them have a fix that follows from the text with nothing guessed. Those
carry a `Repair`. Everything else carries none, and no button is offered for it:
a fix that is wrong once costs more than every fix it got right.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backsight.engine.plan.diagnostics import Diagnostic

# What the engine names in its own prose, quoted. Every explanation below that
# needs to say *which* argument reads it out of the text rather than guessing.
NAMED = re.compile(r'"([^"]+)"')

# The types that can be rewritten without knowing anything about the value. A
# quoted "map" means a map of strings and always did; that is what the engine
# says to write.
UNQUOTED = {
    "string": "string",
    "number": "number",
    "bool": "bool",
    "map": "map(string)",
    "list": "list(string)",
}

QUOTED_TYPE = re.compile(r'^(?P<before>\s*type\s*=\s*)"(?P<type>\w+)"(?P<after>\s*)$')


@dataclass(frozen=True)
class Repair:
    """One line rewritten, and nothing else touched."""

    line: int
    before: str
    after: str
    label: str


@dataclass(frozen=True)
class Explained:
    """A diagnostic in the reader's language, with the engine's kept beside it."""

    title: str
    explanation: str
    repair: Repair | None = None

    @property
    def is_fixable(self) -> bool:
        return self.repair is not None


def explain(found: Diagnostic, source: str = "") -> Explained:
    """What this diagnostic means, and how to fix it when that is knowable.

    Falls back to the engine's own summary when the shape is not recognised,
    which is the honest answer rather than a worse sentence about a diagnostic
    nobody anticipated.
    """
    write = RULES.get(found.summary)
    if write is None:
        return Explained(title=found.summary, explanation=found.detail)
    return write(found, source)


def _quoted_type(found: Diagnostic, source: str) -> Explained:
    return Explained(
        title="Type constraint is quoted",
        explanation=(
            "Quoted type constraints were dropped after OpenTofu 0.11. Write the "
            "type as an expression instead, and say what the collection contains."
        ),
        repair=_unquote(found, source),
    )


def _unquote(found: Diagnostic, source: str) -> Repair | None:
    """Strips the quotes, when the line really is the one the engine named."""
    line = _line_at(source, found.line)
    if line is None:
        return None
    match = QUOTED_TYPE.match(line)
    if match is None or match.group("type") not in UNQUOTED:
        return None
    written = UNQUOTED[match.group("type")]
    return Repair(
        line=found.line,
        before=line,
        after=f"{match.group('before')}{written}{match.group('after')}",
        label=f"Write it as {written}",
    )


def _missing_argument(found: Diagnostic, _source: str) -> Explained:
    named = NAMED.search(found.detail)
    argument = named.group(1) if named else "an argument"
    return Explained(
        title="A required argument is missing",
        explanation=(
            f"This block will not work without {argument}. Add it inside the "
            "block. Backsight will not write it for you, because only you know "
            "what the value should be."
        ),
    )


def _unsupported_argument(found: Diagnostic, _source: str) -> Explained:
    named = NAMED.search(found.detail)
    argument = named.group(1) if named else "that argument"
    return Explained(
        title="That argument is not recognised",
        explanation=(
            f"Nothing here accepts {argument}. It is usually a misspelling, or an "
            "argument that belongs in a different block. Check the spelling before "
            "deleting the line."
        ),
    )


def _undeclared_variable(found: Diagnostic, _source: str) -> Explained:
    named = NAMED.search(found.detail)
    variable = named.group(1) if named else "that variable"
    return Explained(
        title="A variable is used but never declared",
        explanation=(
            f"Something reads {variable} and no variable block declares it. Declare "
            "it, or correct the name if it was a typo."
        ),
    )


def _not_initialised(_found: Diagnostic, _source: str) -> Explained:
    return Explained(
        title="This workspace has not been initialised",
        explanation=(
            "The providers and modules this configuration needs have not been "
            "downloaded yet. Initialising does that, and changes nothing that is "
            "running."
        ),
    )


def _line_at(source: str, number: int) -> str | None:
    if not source or number < 1:
        return None
    lines = source.splitlines()
    return lines[number - 1] if number <= len(lines) else None


# Keyed on what the engine writes after `Error:`. Only summaries with a real
# capture in `fixtures/plan-failures/` appear here — a rule written from memory
# is a rule that fires on output nobody has seen.
RULES = {
    "Invalid quoted type constraints": _quoted_type,
    "Missing required argument": _missing_argument,
    "Unsupported argument": _unsupported_argument,
    "Reference to undeclared input variable": _undeclared_variable,
    "Inconsistent dependency lock file": _not_initialised,
}
