"""Reading HCL by its syntax tree rather than by pattern matching.

Text matching gets a backend block right until somebody writes one inside a
comment, and gets a module source right until the path contains an equals sign.
Everything that asks a question about HCL asks it here.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import tree_sitter_hcl
from tree_sitter import Language, Node, Parser


@cache
def _parser() -> Parser:
    """One parser, built once. Building the language is not cheap."""
    return Parser(Language(tree_sitter_hcl.language()))


@dataclass(frozen=True)
class Block:
    """One `type "label" "label" { ... }` in a file."""

    type: str
    labels: tuple[str, ...]
    node: Node
    source: bytes

    @property
    def body(self) -> Node | None:
        return next((c for c in self.node.children if c.type == "body"), None)

    def blocks(self, type_: str | None = None) -> list[Block]:
        return blocks(self.body, self.source, type_)

    def attributes(self) -> dict[str, str]:
        return attributes(self.body, self.source)


def parse(source: bytes) -> Node:
    """The root node of a file. Invalid HCL still parses; it parses with errors."""
    return _parser().parse(source).root_node


def body_of(source: bytes) -> Node | None:
    """The top-level body of a file.

    Leading comments are siblings of the body rather than part of it, so taking
    the root's first child returns a comment for any file that opens with one —
    and every block in it then goes unseen.
    """
    root = parse(source)
    return next((c for c in root.children if c.type == "body"), None)


def text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", "replace")


def _string(node: Node, source: bytes) -> str:
    """The content of a string literal, without its quotes."""
    literal = next((c for c in node.children if c.type == "template_literal"), None)
    return text(literal, source) if literal is not None else ""


def _first(node: Node, kind: str) -> Node | None:
    if node.type == kind:
        return node
    for child in node.children:
        found = _first(child, kind)
        if found is not None:
            return found
    return None


def blocks(body: Node | None, source: bytes, type_: str | None = None) -> list[Block]:
    """The blocks directly inside a body, optionally only those of one type."""
    if body is None:
        return []
    found = []
    for child in body.children:
        if child.type != "block":
            continue
        identifier = next((c for c in child.children if c.type == "identifier"), None)
        if identifier is None:
            continue
        name = text(identifier, source)
        if type_ is not None and name != type_:
            continue
        labels = tuple(_string(c, source) for c in child.children if c.type == "string_lit")
        found.append(Block(type=name, labels=labels, node=child, source=source))
    return found


def attributes(body: Node | None, source: bytes) -> dict[str, str]:
    """Attribute name to the raw text of its value, in order."""
    if body is None:
        return {}
    found = {}
    for child in body.children:
        if child.type != "attribute":
            continue
        identifier = next((c for c in child.children if c.type == "identifier"), None)
        expression = next((c for c in child.children if c.type == "expression"), None)
        if identifier is not None and expression is not None:
            found[text(identifier, source)] = text(expression, source)
    return found


def string_attribute(body: Node | None, source: bytes, name: str) -> str | None:
    """One attribute's value, when it is a plain quoted string and nothing else."""
    if body is None:
        return None
    for child in body.children:
        if child.type != "attribute":
            continue
        identifier = next((c for c in child.children if c.type == "identifier"), None)
        if identifier is None or text(identifier, source) != name:
            continue
        expression = next((c for c in child.children if c.type == "expression"), None)
        if expression is None:
            return None
        literal = _first(expression, "string_lit")
        return _string(literal, source) if literal is not None else None
    return None


def object_attribute(body: Node | None, source: bytes, name: str) -> dict[str, str]:
    """The string entries of an attribute whose value is an object literal.

    `aws = { source = "hashicorp/aws", version = "~> 5.82" }` gives back the two
    entries. Anything that is not a plain string is left out rather than guessed.
    """
    if body is None:
        return {}
    for child in body.children:
        if child.type != "attribute":
            continue
        identifier = next((c for c in child.children if c.type == "identifier"), None)
        if identifier is None or text(identifier, source) != name:
            continue
        expression = next((c for c in child.children if c.type == "expression"), None)
        obj = _first(expression, "object") if expression is not None else None
        if obj is None:
            return {}
        entries = {}
        for element in (c for c in obj.children if c.type == "object_elem"):
            parts = [c for c in element.children if c.type == "expression"]
            if len(parts) != 2:
                continue
            key = _first(parts[0], "identifier") or _first(parts[0], "string_lit")
            value = _first(parts[1], "string_lit")
            if key is None or value is None:
                continue
            key_text = _string(key, source) if key.type == "string_lit" else text(key, source)
            entries[key_text] = _string(value, source)
        return entries
    return {}
