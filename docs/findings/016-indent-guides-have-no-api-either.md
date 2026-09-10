# Finding 016 — indent guides have no API either, and the dead keys now answer

**Status: decided, 2026-09-09 — a fourth capability joins finding 002, and the three that were already there stopped being silent.**

## The fourth

The v2 design asks for **one indent guide, on the enclosing block only** — not a
guide at every level, which in a language that nests two or three deep is noise.

`GtkSource.View` has no such API. Checked against the installed 5.12, method by
method: there is `set_background_pattern`, which draws a **grid** over the whole
buffer and is a different thing, and there is nothing else. So it joins the
three in [002](002-three-baseline-capabilities-have-no-api.md):

| Wanted | State |
|---|---|
| Multiple cursors | no API |
| Column selection | no API |
| Code folding | none at all — not partial, none |
| **Indent guides** | **no API** |

## What changed, which is not the capability

002 decided these are not built and said the menu items should say so. They did.
What nobody had designed is **what happens when somebody reaches for one without
opening a menu**, and that is the worst moment this application has: a keystroke
from VS Code muscle memory that does nothing at all.

Three things answer it now.

**`Ctrl+D` does the useful half.** It selects the next occurrence of the word
under the caret — which is a real command, on the key people press for it — and
says once, in a dismissible line, that multiple cursors are not available and
what does most of what they are reached for. Once per session, never again.

**Every blocked menu item carries its own reason** on the item rather than being
greyed mutely, which 002 already asked for and which now includes the fourth.

**Help → What Backsight will not do** is a page listing all four toolkit limits,
the four things this application refuses on purpose, and the three that are
simply not built yet. Products almost never write this page. This one had
already written the reasoning, in this folder, and had no way for a person to
read it.

## Why not build the guide by drawing it

It could be drawn: a `GutterRenderer` knows where a line starts and the buffer
knows its indentation, so a one-pixel rule at the right column is not hard.

**It would be drawn in the wrong place the moment anything moved.** The guide
has to track the *enclosing block*, which means asking the syntax tree where the
caret is on every cursor move, and then drawing inside the text area rather than
the gutter — which is where `add_overlay` puts a widget in buffer coordinates
and where the annotation lane already lives. Two overlay systems competing for
the same rows, to draw a line.

The cost is not the drawing. It is that a guide which is subtly wrong about
where a block starts is worse than no guide, because it is read as structure.

## What this does not change

The gutter still holds the twelve pixels code folding would need. Nothing
reflows the day the toolkit grows the API, and that is the cheapest promise in
the whole editor.
