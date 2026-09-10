"""Who did something, which is never the same question as who is logged in.

BRD §12 puts a service that acts on behalf of a person in v2. Code that reaches
for a username instead of an actor works today and has to be found and rewritten
everywhere on the day that service exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActorKind(Enum):
    """Whether a person did this themselves, or something did it for them."""

    PERSON = "person"
    SERVICE = "service"


@dataclass(frozen=True)
class Actor:
    """The party responsible for an action, and the party that performed it."""

    kind: ActorKind
    identifier: str
    on_behalf_of: str | None = None

    def __post_init__(self) -> None:
        if not self.identifier:
            raise ValueError("an actor needs an identifier")
        if self.kind is ActorKind.PERSON and self.on_behalf_of is not None:
            raise ValueError("a person acts as themselves, not on behalf of somebody")

    @property
    def responsible(self) -> str:
        """The person answerable for the action, whoever carried it out."""
        return self.on_behalf_of or self.identifier
