"""The blocks people write most often, as text rather than as a template engine.

Each one is what a person would type, with the parts they must fill in left as
obvious placeholders. There is no tab-through-the-fields machinery: that is a
whole feature, and a snippet that inserts correct HCL is most of the value.

The indentation is two spaces, which is the Terraform convention and what
`tofu fmt` produces. A snippet that arrives needing reformatting teaches the
wrong thing on the way in.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Snippet:
    """One block, and the name the menu and the palette call it."""

    name: str
    label: str
    body: str


SNIPPETS: tuple[Snippet, ...] = (
    Snippet(
        name="snippet-resource",
        label="Resource",
        body='resource "TYPE" "NAME" {\n  \n}\n',
    ),
    Snippet(
        name="snippet-variable",
        label="Variable",
        body=('variable "NAME" {\n  type        = string\n  description = "WHAT IT IS FOR"\n}\n'),
    ),
    Snippet(
        name="snippet-output",
        label="Output",
        body=('output "NAME" {\n  value       = EXPRESSION\n  description = "WHAT IT IS FOR"\n}\n'),
    ),
    Snippet(
        name="snippet-module",
        label="Module call",
        body='module "NAME" {\n  source = "./PATH"\n}\n',
    ),
)

BY_NAME = {snippet.name: snippet for snippet in SNIPPETS}


def body_of(name: str) -> str | None:
    """The text to insert, or None for a name nothing declares."""
    snippet = BY_NAME.get(name)
    return snippet.body if snippet else None
