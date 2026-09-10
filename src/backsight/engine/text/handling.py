"""Indentation, line endings, encoding and whitespace — all on request.

The text-handling row. Every one of these rewrites a file wholesale, which
is exactly what FR-ED-07 forbids doing on somebody's behalf, so each is an
explicit action and none of them runs on save unless the setting says so.

`trim_trailing_whitespace` and `ensure_final_newline` are the two people expect
on save, and both are on by default — they are the only rewrites here that
cannot change what a file means. Everything else is an explicit action.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backsight.engine.text.lines import join, split


class LineEnding(Enum):
    """What sits at the end of each line."""

    LF = "\n"
    CRLF = "\r\n"

    @property
    def label(self) -> str:
        return {"\n": "LF", "\r\n": "CRLF"}[self.value]


@dataclass(frozen=True)
class Indentation:
    """How a file is indented, as it actually is rather than as configured."""

    uses_tabs: bool
    width: int

    @property
    def label(self) -> str:
        return "Tabs" if self.uses_tabs else f"Spaces: {self.width}"


def detect_line_ending(text: str) -> LineEnding:
    """The ending most of the file uses. Mixed files keep their majority."""
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    return LineEnding.CRLF if crlf > lf else LineEnding.LF


def is_mixed(text: str) -> bool:
    """Worth saying out loud: a mixed file will surprise somebody later."""
    crlf = text.count("\r\n")
    return bool(crlf) and bool(text.count("\n") - crlf)


def convert_line_endings(text: str, to: LineEnding) -> str:
    normalised = text.replace("\r\n", "\n")
    return normalised if to is LineEnding.LF else normalised.replace("\n", "\r\n")


def detect_indentation(text: str, *, default_width: int = 2) -> Indentation:
    """Reads the file rather than trusting a setting.

    Opening somebody's tab-indented module and inserting spaces into it because
    a preference said so is the same class of damage as reformatting on save.
    """
    tabs = spaces = 0
    widths: list[int] = []
    for line in split(text):
        if not line.strip():
            continue
        lead = line[: len(line) - len(line.lstrip())]
        if lead.startswith("\t"):
            tabs += 1
        elif lead:
            spaces += 1
            widths.append(len(lead))
    if tabs > spaces:
        return Indentation(uses_tabs=True, width=default_width)
    return Indentation(uses_tabs=False, width=_common_step(widths) or default_width)


def _common_step(widths: list[int]) -> int:
    """The smallest difference between successive indent levels."""
    steps = {abs(b - a) for a, b in zip(sorted(set(widths)), sorted(set(widths))[1:], strict=False)}
    steps.discard(0)
    return min(steps) if steps else 0


def convert_indentation(text: str, *, to_tabs: bool, width: int) -> str:
    """Only the leading whitespace of each line. Nothing inside a string moves."""
    out = []
    for line in split(text):
        lead_length = len(line) - len(line.lstrip("\t "))
        lead, body = line[:lead_length], line[lead_length:]
        columns = sum(width if character == "\t" else 1 for character in lead)
        out.append(("\t" * (columns // width) if to_tabs else " " * columns) + body)
    return join(out)


def trim_trailing_whitespace(text: str) -> str:
    """Trailing spaces only. The final newline, or its absence, is left alone."""
    return join([line.rstrip(" \t") for line in split(text)])


def ensure_final_newline(text: str) -> str:
    """A file ends in a newline, which is what every other tool assumes.

    An empty file is left empty: a lone newline in a file somebody has not
    written anything into is a change nobody asked for.
    """
    if not text or text.endswith("\n"):
        return text
    return text + "\n"


def on_save(text: str, *, trim: bool = True, final_newline: bool = True) -> str:
    """Everything that runs on save, in the order it has to run.

    Trimming first, because adding the final newline to a file whose last line
    is spaces would otherwise leave those spaces behind forever.
    """
    if trim:
        text = trim_trailing_whitespace(text)
    if final_newline:
        text = ensure_final_newline(text)
    return text


def decode(data: bytes, encoding: str) -> str:
    """Reopening a file with a stated encoding, which is a deliberate act."""
    return data.decode(encoding)


def encodings() -> tuple[str, ...]:
    """What "reopen with encoding" offers. Short on purpose."""
    return ("utf-8", "utf-16", "latin-1", "cp1252", "iso-8859-15")
