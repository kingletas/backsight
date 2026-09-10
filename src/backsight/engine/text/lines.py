"""Line and comment operations, as text in and text out.

The baseline. None of it is novel and all of it is required — an editor
missing these is one nobody can use for an hour.

Kept as pure functions so every one is tested without a window, and so the
round-trip rule holds by construction: each returns the original text with one
span replaced, and nothing else is rewritten on the way past.

**Lines are split on `\\n` alone.** `str.splitlines` also breaks on `\\v`, `\\f`
and `U+2028`, which appear inside HCL heredocs and would be silently converted
into line breaks. A CRLF file keeps its `\\r` as the last character of each line
and comes back out unchanged.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable, MutableSequence
from dataclasses import dataclass

# Comment markers, in the order a toggle tries them. `#` is what `tofu fmt`
# produces, so it is what gets written.
LINE_COMMENT = "#"
ALSO_A_LINE_COMMENT = "//"
BLOCK_OPEN, BLOCK_CLOSE = "/*", "*/"


@dataclass(frozen=True)
class Span:
    """A run of whole lines, zero-based and inclusive at both ends."""

    first: int
    last: int

    def __post_init__(self) -> None:
        if self.first < 0 or self.last < self.first:
            raise ValueError(f"a span runs forwards, got {self.first}..{self.last}")

    @property
    def count(self) -> int:
        return self.last - self.first + 1

    def shifted(self, by: int) -> Span:
        return Span(first=max(0, self.first + by), last=max(0, self.last + by))


def split(text: str) -> list[str]:
    return text.split("\n")


def join(parts: list[str]) -> str:
    return "\n".join(parts)


def last_line(parts: list[str]) -> int:
    """The index of the last real line.

    Splitting `"a\n"` gives `["a", ""]`. That final empty element is the text
    after the last newline, not a line — treating it as one lets a span select
    a line that is not there, and lets `move` push a line past the end.
    """
    if len(parts) > 1 and parts[-1] == "":
        return len(parts) - 2
    return max(0, len(parts) - 1)


def _bounded(parts: list[str], span: Span) -> Span:
    end = last_line(parts)
    return Span(first=min(span.first, end), last=min(span.last, end))


# --- lines ----------------------------------------------------------------


def duplicate(text: str, span: Span) -> tuple[str, Span]:
    """Copies the lines below themselves; the selection follows the copy."""
    parts = split(text)
    span = _bounded(parts, span)
    chosen = parts[span.first : span.last + 1]
    parts[span.last + 1 : span.last + 1] = chosen
    return join(parts), span.shifted(span.count)


def delete(text: str, span: Span) -> tuple[str, Span]:
    parts = split(text)
    span = _bounded(parts, span)
    del parts[span.first : span.last + 1]
    if not parts:
        parts = [""]
    landing = min(span.first, len(parts) - 1)
    return join(parts), Span(first=landing, last=landing)


def join_lines(text: str, span: Span) -> tuple[str, Span]:
    """Runs the span onto one line, with single spaces and no leading indent."""
    parts = split(text)
    span = _bounded(parts, span)
    # One line joins the next one up; a selection joins exactly what it covers.
    last = min(span.last + 1, last_line(parts)) if span.count == 1 else span.last
    if last <= span.first:
        return text, span
    chosen = parts[span.first : last + 1]
    merged = chosen[0].rstrip()
    for line in chosen[1:]:
        stripped = line.strip()
        merged = f"{merged} {stripped}" if stripped else merged
    parts[span.first : last + 1] = [merged]
    return join(parts), Span(first=span.first, last=span.first)


def move(text: str, span: Span, *, by: int) -> tuple[str, Span]:
    """Moves the span up or down. At either end it stays where it is."""
    parts = split(text)
    span = _bounded(parts, span)
    target = span.first + by
    if target < 0 or span.last + by > last_line(parts):
        return text, span
    chosen = parts[span.first : span.last + 1]
    del parts[span.first : span.last + 1]
    parts[target:target] = chosen
    return join(parts), span.shifted(by)


def swap(text: str, span: Span) -> tuple[str, Span]:
    """Exchanges the first and last lines of the span."""
    parts = split(text)
    span = _bounded(parts, span)
    if span.count < 2:
        return text, span
    parts[span.first], parts[span.last] = parts[span.last], parts[span.first]
    return join(parts), span


def sort(
    text: str, span: Span, *, case_sensitive: bool = False, reverse: bool = False
) -> tuple[str, Span]:
    parts = split(text)
    span = _bounded(parts, span)
    chosen = parts[span.first : span.last + 1]
    key = None if case_sensitive else str.casefold
    parts[span.first : span.last + 1] = sorted(chosen, key=key, reverse=reverse)
    return join(parts), span


def reverse(text: str, span: Span) -> tuple[str, Span]:
    parts = split(text)
    span = _bounded(parts, span)
    parts[span.first : span.last + 1] = list(reversed(parts[span.first : span.last + 1]))
    return join(parts), span


def unique(text: str, span: Span) -> tuple[str, Span]:
    """Removes repeats, keeping the first of each and the original order."""
    parts = split(text)
    span = _bounded(parts, span)
    seen: set[str] = set()
    kept = []
    for line in parts[span.first : span.last + 1]:
        if line not in seen:
            seen.add(line)
            kept.append(line)
    parts[span.first : span.last + 1] = kept
    return join(parts), Span(first=span.first, last=span.first + max(0, len(kept) - 1))


def shuffle(
    text: str, span: Span, *, shuffler: Callable[[MutableSequence[str]], None] | None = None
) -> tuple[str, Span]:
    """Reorders the span. The shuffler is a parameter so a test can be certain.

    The default comes from `secrets` rather than `random` — not because
    shuffling lines needs to be unguessable, but because taking the ordinary
    generator means telling a scanner to look away, and a rule with exceptions
    stops being read.
    """
    parts = split(text)
    span = _bounded(parts, span)
    chosen = parts[span.first : span.last + 1]
    (shuffler or secrets.SystemRandom().shuffle)(chosen)
    parts[span.first : span.last + 1] = chosen
    return join(parts), span


# --- comments -------------------------------------------------------------


def _is_commented(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith((LINE_COMMENT, ALSO_A_LINE_COMMENT))


def toggle_line_comment(text: str, span: Span) -> tuple[str, Span]:
    """Comments the span, or uncomments it if every non-blank line already is.

    Toggling on a mixed selection comments everything, which is what every other
    editor does and what people expect when they hit the key twice.
    """
    parts = split(text)
    span = _bounded(parts, span)
    chosen = parts[span.first : span.last + 1]
    meaningful = [line for line in chosen if line.strip()]
    all_commented = bool(meaningful) and all(_is_commented(line) for line in meaningful)

    if all_commented:
        parts[span.first : span.last + 1] = [_uncomment(line) for line in chosen]
    else:
        indent = min(
            (len(line) - len(line.lstrip()) for line in meaningful),
            default=0,
        )
        parts[span.first : span.last + 1] = [
            line if not line.strip() else f"{line[:indent]}{LINE_COMMENT} {line[indent:]}"
            for line in chosen
        ]
    return join(parts), span


def _uncomment(line: str) -> str:
    if not line.strip():
        return line
    indent_length = len(line) - len(line.lstrip())
    indent, body = line[:indent_length], line[indent_length:]
    for marker in (LINE_COMMENT, ALSO_A_LINE_COMMENT):
        if body.startswith(marker):
            body = body[len(marker) :]
            # A single space after the marker is ours; anything more is theirs.
            if body.startswith(" "):
                body = body[1:]
            return indent + body
    return line


def toggle_block_comment(text: str, span: Span) -> tuple[str, Span]:
    """Wraps the span in `/* */`, or unwraps it when it already is."""
    parts = split(text)
    span = _bounded(parts, span)
    chosen = parts[span.first : span.last + 1]
    first, last = chosen[0].strip(), chosen[-1].strip()

    if first.startswith(BLOCK_OPEN) and last.endswith(BLOCK_CLOSE):
        chosen[0] = (
            chosen[0].replace(BLOCK_OPEN, "", 1).lstrip(" ") if len(chosen) > 1 else chosen[0]
        )
        if len(chosen) == 1:
            body = chosen[0].strip()
            body = body[len(BLOCK_OPEN) : -len(BLOCK_CLOSE)].strip()
            indent = chosen[0][: len(chosen[0]) - len(chosen[0].lstrip())]
            parts[span.first : span.last + 1] = [indent + body]
            return join(parts), span
        tail = chosen[-1].rstrip()
        chosen[-1] = tail[: -len(BLOCK_CLOSE)].rstrip()
        parts[span.first : span.last + 1] = chosen
        return join(parts), span

    indent_length = len(chosen[0]) - len(chosen[0].lstrip())
    indent = chosen[0][:indent_length]
    if len(chosen) == 1:
        parts[span.first] = f"{indent}{BLOCK_OPEN} {chosen[0].strip()} {BLOCK_CLOSE}"
    else:
        chosen[0] = f"{indent}{BLOCK_OPEN} {chosen[0][indent_length:]}"
        chosen[-1] = f"{chosen[-1]} {BLOCK_CLOSE}"
        parts[span.first : span.last + 1] = chosen
    return join(parts), span


def reindent(text: str, to: str) -> str:
    """Re-indents a block so its shallowest line sits at `to`.

    The shape inside the block is kept: a nested line stays nested relative to
    its neighbours. Only the whole block moves, which is what "paste and
    indent" means and what re-indenting every line to the same depth does not.
    """
    if not text:
        return text
    lines = text.split("\n")
    filled = [line for line in lines if line.strip()]
    if not filled:
        return text
    common = min(len(line) - len(line.lstrip()) for line in filled)
    moved = []
    for index, line in enumerate(lines):
        if not line.strip():
            moved.append("")
            continue
        stripped = line[common:]
        # The first line goes where the caret already is, so it is not indented
        # again — everything after it is placed relative to that.
        moved.append(stripped if index == 0 else to + stripped)
    return "\n".join(moved)


def indentation_of(line: str) -> str:
    """The leading whitespace of a line, exactly as written."""
    return line[: len(line) - len(line.lstrip())]
