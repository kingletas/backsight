"""Putting the completion engine in front of somebody typing.

`engine/schema/completion.py` has decided what can be written at a position
since it was built, under a latency budget, with its own tests — and nothing in
the editor ever called it. The same shape as the keymap that described every
shortcut and installed none: a feature that exists, passes, and cannot be
reached.

This is the adapter and nothing else. What to offer is the engine's decision;
this turns it into rows GtkSourceView can draw.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("GtkSource", "5")

from gi.repository import Gio, GObject, Gtk, GtkSource

from backsight.engine.schema.completion import Candidate, Kind, complete

# A word character in HCL. The provider is asked to complete from here back.
WORD = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-."

# What each kind is called in the list, in the reader's words rather than the
# parser's. `Kind.RESOURCE_TYPE` is "resource" to somebody writing one.
CALLED = {
    Kind.TOP_LEVEL: "block",
    Kind.RESOURCE_TYPE: "resource",
    Kind.DATA_TYPE: "data source",
    Kind.ARGUMENT: "argument",
}


class Proposal(GObject.Object, GtkSource.CompletionProposal):
    """One candidate, carried through GtkSourceView's list."""

    def __init__(self, candidate: Candidate) -> None:
        super().__init__()
        self.candidate = candidate


class Completions(GObject.Object, GtkSource.CompletionProvider):
    """Offers what the engine says can be written here.

    Silent when there is no schema index. An index is built from providers that
    have been initialised, so a workspace nobody has run `init` in has none —
    and a completion popup that opens empty is worse than one that never opens.
    """

    def __init__(self, index_for) -> None:
        super().__init__()
        self._index_for = index_for

    def do_get_title(self) -> str:
        return "Terraform"

    def do_get_priority(self, _context) -> int:
        return 100

    def do_is_trigger(self, _iter, character: str) -> bool:
        """Opens on a dot, which is where a resource type is being written."""
        return character == "."

    def do_populate_async(self, context, cancellable, callback, data=None) -> None:
        task = Gio.Task.new(self, cancellable, callback, data)
        index = self._index_for()
        if index is None:
            task.return_value(Gtk.StringList())
            return
        found = self._candidates(context, index)
        store = Gio.ListStore.new(Proposal)
        for candidate in found:
            store.append(Proposal(candidate))
        task.return_value(store)

    def do_populate_finish(self, result):
        return result.propagate_value()[1]

    def do_display(self, _context, proposal, cell) -> None:
        candidate = proposal.candidate
        column = cell.get_column()
        if column == GtkSource.CompletionColumn.TYPED_TEXT:
            cell.set_text(candidate.label)
        elif column == GtkSource.CompletionColumn.DETAILS:
            cell.set_text(candidate.description or candidate.detail or None)
        elif column == GtkSource.CompletionColumn.AFTER:
            # Required arguments have to be distinguishable from optional ones
            # by something other than order — FR-SCH-09.
            cell.set_text(candidate.type_label or ("required" if candidate.required else None))
        elif column == GtkSource.CompletionColumn.BEFORE:
            cell.set_text(CALLED.get(candidate.kind))

    def do_activate(self, context, proposal) -> None:
        """Replaces the word being typed, rather than appending to it."""
        buffer = context.get_buffer()
        found, start, end = context.get_bounds()
        buffer.begin_user_action()
        if found:
            buffer.delete(start, end)
        buffer.insert(buffer.get_iter_at_mark(buffer.get_insert()), proposal.candidate.label)
        buffer.end_user_action()

    def _candidates(self, context, index) -> list[Candidate]:
        buffer = context.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        caret = buffer.get_iter_at_mark(buffer.get_insert())
        offset = len(text[: caret.get_offset()].encode("utf-8"))
        try:
            found = complete(text.encode("utf-8"), offset, index)
        except Exception:  # noqa: BLE001
            # Typing produces half-written files constantly. A parser that
            # cannot read one must cost the popup, never the keystroke.
            return []
        return sorted(found, key=lambda candidate: candidate.sort_key)


def install(view: GtkSource.View, index_for) -> Completions:
    """Puts the provider on one view and hands it back for testing."""
    provider = Completions(index_for)
    view.get_completion().add_provider(provider)
    return provider
