"""The two labels on a block header, told apart by reading the syntax tree.

`resource "aws_instance" "api"` carries two quoted words and they are different
kinds of thing: the first is the provider's vocabulary and the second is a name
you chose. **Telling those apart is most of what reading HCL is**, and they were
drawn in one colour.

Changing the scheme did not fix it, and the reason is worth writing down.
GtkSourceView's own `terraform.lang` captures the block header as

    (^\\s*(?P<title>identifier)\\s+)?(?P<label>("?identifier"?\\s*)*)\\{

— so `title` is the **keyword** and `label` is *both* quoted words in one span.
The grammar has no separate capture for the type, so no colour scheme can give
them different colours. The fix has to happen where the two are actually
distinguishable, and that is the parser this product already trusts for every
other question it asks about HCL.

So the labels are tagged from the tree: **two or more labels means the first is
a type and the rest are names; one label is a name.** `module "vpc"` names a
thing you called `vpc`, and colouring that as provider vocabulary would be a
confident lie about a very common line.

The alternative was shipping a modified copy of GtkSourceView's language spec.
It is LGPL and this project is MIT, so that is a licensing decision rather than
a technical one — and it is not needed, because the tree is better than the
regex would have been anyway.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import GLib, GtkSource

from backsight.app.theme import tokens
from backsight.engine.hcl import parse

TYPE = "backsight-block-type"
NAME = "backsight-block-name"

# Past this a file is large enough that re-reading its tree on every keystroke
# is felt, and the labels are worth less than the typing is. The whole of
# `~/Development/terraform` is under it; the number is a ceiling rather than a
# target.
LONGEST = 400_000


def spans(source: bytes) -> list[tuple[int, int, int, int, str]]:
    """Every block label, as (line, start column, end column, byte length, kind).

    Columns are in **characters**, which is what a text buffer counts in — the
    tree counts bytes, and a comment with an accent in it is enough to put the
    two out of step.
    """
    found: list[tuple[int, int, int, int, str]] = []
    for block in parse.blocks(parse.body_of(source), source):
        labels = [child for child in block.node.children if child.type == "string_lit"]
        for at, node in enumerate(labels):
            kind = "type" if at == 0 and len(labels) > 1 else "name"
            row = node.start_point[0]
            line = source.split(b"\n")[row] if row < source.count(b"\n") + 1 else b""
            start = len(line[: node.start_point[1]].decode("utf-8", "replace"))
            end = len(line[: node.end_point[1]].decode("utf-8", "replace"))
            found.append((row, start, end, node.end_byte - node.start_byte, kind))
    return found


class Labels:
    """Keeps one buffer's block labels coloured as the tree says they are."""

    def __init__(self, view: GtkSource.View) -> None:
        self._buffer = view.get_buffer()
        self._pending: int | None = None
        self._buffer.connect("changed", lambda *_: self._schedule())
        self._schedule()

    def _schedule(self) -> None:
        if self._pending is not None:
            return
        self._pending = GLib.idle_add(self._apply, priority=GLib.PRIORITY_LOW)

    def _tag(self, name: str, token: str):
        """The tag, with its colour set every time rather than once.

        The desktop can go dark between one keystroke and the next, and a tag
        made in light mode keeps a light-mode colour for the life of the
        buffer. Setting it each pass costs nothing and cannot go stale.
        """
        table = self._buffer.get_tag_table()
        found = table.lookup(name)
        if found is None:
            # Created after the scheme's own tags, so it takes priority over
            # them — which is the whole mechanism, and the reason this is not
            # fighting the highlighter so much as finishing its sentence.
            found = self._buffer.create_tag(name)
        found.set_property("foreground-rgba", tokens.color(token))
        return found

    def clear(self) -> None:
        whole = (self._buffer.get_start_iter(), self._buffer.get_end_iter())
        for name in (TYPE, NAME):
            tag = self._buffer.get_tag_table().lookup(name)
            if tag is not None:
                self._buffer.remove_tag(tag, *whole)

    def _apply(self) -> bool:
        self._pending = None
        self.clear()
        text = self._buffer.get_text(
            self._buffer.get_start_iter(), self._buffer.get_end_iter(), False
        )
        source = text.encode("utf-8")
        if len(source) > LONGEST:
            return False
        try:
            found = spans(source)
        except (ValueError, RecursionError):
            # A file mid-edit is not valid HCL for keystrokes at a time, and a
            # colour is not worth an exception on the drawing thread.
            return False
        tags = {"type": self._tag(TYPE, "syn_type"), "name": self._tag(NAME, "syn_name")}
        for row, start, end, _length, kind in found:
            reached, at = self._buffer.get_iter_at_line_offset(row, start)
            if not reached:
                continue
            _reached, to = self._buffer.get_iter_at_line_offset(row, end)
            self._buffer.apply_tag(tags[kind], at, to)
        return False


def install(view: GtkSource.View) -> Labels:
    return Labels(view)
