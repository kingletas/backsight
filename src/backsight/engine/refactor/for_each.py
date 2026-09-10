"""Converting `count` to `for_each`, with the block that keeps every instance.

FR-REF-04. This is among the most common ways people destroy infrastructure by
accident: `count` addresses instances by position, `for_each` by key, and with
nothing to map one to the other the engine sees every instance disappear and an
equal number of different ones appear.

The mapping is the user's to give. Index 0 becoming key "a" is a fact about
their intent, not something to infer from the order of a map literal.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Conversion:
    """One resource moving from positions to keys."""

    resource_type: str
    name: str
    keys: tuple[str, ...]
    kind: str = "resource"

    def __post_init__(self) -> None:
        if not self.keys:
            raise ValueError("a conversion needs the keys the instances become")
        if len(set(self.keys)) != len(self.keys):
            # Two indices mapping to one key means one instance is being dropped,
            # which the plan would show as a destroy. Refuse before it gets there.
            raise ValueError("two instances cannot become the same key")
        for key in self.keys:
            if not key:
                raise ValueError("an instance cannot become an empty key")

    @property
    def prefix(self) -> str:
        return "" if self.kind == "resource" else "data."

    def old_address(self, index: int) -> str:
        return f"{self.prefix}{self.resource_type}.{self.name}[{index}]"

    def new_address(self, key: str) -> str:
        return f'{self.prefix}{self.resource_type}.{self.name}["{key}"]'


def moved_blocks(conversion: Conversion) -> str:
    """One block per instance, in index order so it reads against the old code."""
    blocks = []
    for index, key in enumerate(conversion.keys):
        blocks.append(
            "\nmoved {\n"
            f"  from = {conversion.old_address(index)}\n"
            f"  to   = {conversion.new_address(key)}\n"
            "}\n"
        )
    return "".join(blocks)


def pairs(conversion: Conversion) -> list[tuple[str, str]]:
    """The mapping, for anything that wants to show it before it is applied."""
    return [
        (conversion.old_address(index), conversion.new_address(key))
        for index, key in enumerate(conversion.keys)
    ]
