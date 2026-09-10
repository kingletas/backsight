# Finding 002 — three of the baseline capabilities have no toolkit API

**Status: decided, 2026-09-08 — not built, and said so. A fourth joined them in [016](016-indent-guides-have-no-api-either.md) on 2026-09-09, which is also where the dead keys stopped being silent.**

Multiple cursors, column selection and code folding are not built and are not
planned. The cost is a rewrite of the editing layer, and what it puts at risk
is round-trip safety and the byte-exact guarantee in `Page.content` — the two
things this editor promises hardest. An editor that occasionally reformats
somebody's file is worse than one missing a feature they can work around.

The menu items say the real reason rather than "not available", and
`select-all-occurrences` says plainly that the toolkit has no multiple cursors
instead of implying an editing mode behind it.

Original finding follows.

**Status when written: needs a decision.** Sheet 9 states the baseline checklist exists as one requirement *"so an implementer cannot treat it as optional polish"*. Three of its items cannot be built on GtkSourceView 5 at all, and saying so is better than quietly shipping nine tenths of a row.

## What is there, and it is most of it

Verified against GtkSourceView 5.12 and GTK 4.14 on this machine.

| Row | State |
|---|---|
| Lines | **Done.** Duplicate, delete, join, move, swap, sort, reverse, unique, shuffle — pure text, tested without a window |
| Comments | **Done.** Line and block, with the toggle behaviour every editor has |
| Find | **Done.** `GtkSource.SearchContext` gives regex, case, whole word, wrap, replace-all with a count |
| Display | **Done.** Line numbers, current line, rulers, wrap and wrap column, whitespace via `SpaceDrawer`, bracket matching |
| Text handling | **Done.** Indentation detected from the file rather than imposed, tabs and spaces conversion, line endings, encoding, trailing whitespace |
| History | **Done.** Undo, redo, one user action per operation |
| Navigation | Partly. Go to line, matching bracket and definition exist; bookmarks and back/forward are not built |
| Clipboard | Not built. Paste from history and paste-and-indent are ours to write |
| Selection | **Three items impossible.** See below |
| Folding | **Impossible.** See below |

## The three with no API

**Code folding.** `GtkSource.View` and `GtkSource.Buffer` expose no folding at all — not a partial API, none. It was dropped and never returned. Folding an HCL block would mean drawing our own gutter, hiding line ranges in a `Gtk.TextView` that has no concept of hidden lines, and reimplementing scrolling and selection over the result.

**Multiple cursors and multiple selections.** `Gtk.TextView` has exactly one insertion point. There is no API for a second. Adding them means intercepting every editing operation, every movement key and every clipboard action, and applying each to a list of positions — which is a rewrite of the editing layer rather than a feature added to it.

**Column selection.** Same root cause: one selection, defined by two iterators over a linear buffer.

## What each would cost

| | Cost | What it risks |
|---|---|---|
| Folding | Large. A custom gutter plus line hiding | Scroll, selection and the verdict bands all assume every line has a position |
| Multiple cursors | Largest. Every edit path reimplemented | Round-trip safety, undo grouping, and the byte-exact guarantee in `Page.content` |
| Column selection | Medium, and it needs multiple cursors first | — |

## Recommended

**Say so, rather than build them now.** The honest position is that Backsight has an editor good for an hour's work and is missing three things people coming from VS Code will notice. Two options, and it is a product decision:

1. **Accept the gap for v1** and record it in the README's "not built yet", where the prototype framing already lives.
2. **Reconsider the toolkit for the editor** — an embedded editor component with these built in. §9.1 rules out anything with a browser engine, which removes Monaco and CodeMirror, so this likely means a custom widget. Sheet OQ-6 asked whether GtkSourceView was sufficient and the answer in the first spike was yes *for the annotation density*. This is the other half of that question, and it has a different answer.

**Nothing about this blocks the rest of sheet 9.** The menu bar, the settings dialog and the settings precedence chain are unaffected.
