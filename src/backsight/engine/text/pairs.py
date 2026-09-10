"""Auto-closing brackets and quotes, and knowing when not to.

The feature is nearly free to add and very easy to make infuriating. Three
rules keep it out of the way:

1. **Never close where a word follows.** Typing `(` before an existing token
   almost always means wrapping it, not opening an empty pair.
2. **Typing the closer that is already there moves over it** rather than adding
   a second one, which is the behaviour that makes it feel like nothing
   happened.
3. **A quote is only a pair when it opens one.** An apostrophe in prose and the
   second `"` of a string are not openings, and doubling them is the thing that
   makes people turn the feature off.

The decision is here so it can be tested without a widget in the room.
"""

from __future__ import annotations

from dataclasses import dataclass

PAIRS = {"(": ")", "[": "]", "{": "}", '"': '"'}
CLOSERS = {closer for closer in PAIRS.values()}

# After one of these, a bracket is opening something rather than wrapping it.
OPENS_BEFORE = " \t\n)]},;"


@dataclass(frozen=True)
class Typed:
    """What to do about one character somebody typed."""

    insert: str = ""
    step_over: bool = False
    # The character that was typed, so a caller stepping over it can check it
    # really is the one in front of the caret before deleting anything.
    character: str = ""

    @property
    def is_nothing(self) -> bool:
        return not self.insert and not self.step_over


NOTHING = Typed()


def typed(character: str, before: str, after: str) -> Typed:
    """What should happen when this character is typed at this position.

    `before` and `after` are the text either side of the caret on its line.
    """
    if character and character in CLOSERS and after[:1] == character:
        # Already there. Typing it again should feel like moving the caret.
        return Typed(step_over=True, character=character)

    if character not in PAIRS:
        return NOTHING

    if character == '"':
        return Typed(insert='"') if _opens_a_string(before, after) else NOTHING

    if after[:1] and after[0] not in OPENS_BEFORE:
        # A word follows, so this is a wrap rather than an empty pair.
        return NOTHING
    return Typed(insert=PAIRS[character])


def wrapping(character: str, selection: str) -> str:
    """What a selection becomes when a pair character is typed over it.

    Wrapping is the one case where a selection is not simply replaced, and it
    is the reason people leave the feature on.
    """
    if character not in PAIRS or not selection:
        return ""
    return f"{character}{selection}{PAIRS[character]}"


def _opens_a_string(before: str, after: str) -> bool:
    """Whether this quote starts a string rather than ending or escaping one."""
    if before.endswith("\\"):
        return False
    if _quotes_in(before) % 2 == 1:
        # A string is already open on this line, so this one closes it.
        return False
    return not (after[:1] and after[0] not in OPENS_BEFORE)


def _quotes_in(text: str) -> int:
    """How many real quotes are in the text, ignoring escaped ones."""
    count = 0
    escaped = False
    for character in text:
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == '"':
            count += 1
    return count
