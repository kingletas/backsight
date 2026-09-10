# Finding 018 — the occurrence outline is an underline, and that is a substitution

**Status: declared, 2026-09-10 — a fifth toolkit substitution, previously undeclared.**

## What the design asks for

*Selection, brackets and guides* — every other occurrence of the word under the
caret takes **a one-pixel accent outline with no fill**. No fill matters more
than the outline does: an occurrence sits on top of the current-line wash and
inside the spine's block, and a filled highlight would stack with both.

## What ships

`Pango.Underline.SINGLE`, in `app/occurrences.py`.

`Gtk.TextTag` has no border property. The full set that could carry an outline
is `background`, `foreground`, `underline`, `strikethrough`, `overline` and
`paragraph-background` — none of them draws a box. Drawing one would mean a
`GtkSourceView` snapshot override computing the rectangle of every match on
every redraw, which is a real amount of code for a one-pixel line.

## Why the substitution is honest

**It keeps the part that was load-bearing.** The rule is *no fill*, so nothing
stacks with the wash or the spine, and an underline satisfies that where a
background would not. What it loses is the shape of the mark, not its meaning.

## Why it is written down anyway

It was in the module's own docstring and in no list anybody reads. The four
declared limits are in [002](002-three-baseline-capabilities-have-no-api.md)
and [016](016-indent-guides-have-no-api-either.md); an undeclared substitution
is how a design quietly becomes advisory, so this is the fifth.
