# Spike 001 — can GtkSourceView carry a line-anchored verdict?

**Question.** BRD OQ-6, named as the largest technical unknown in P1. FR-ED-05 wants a finding rendered against the line of HCL that caused it, in the density plate 01 shows. Can GtkSourceView 5 do that, or does the editor need a custom text widget?

**Answer.** GtkSourceView is sufficient, using `Gtk.TextView`'s own overlay mechanism. No custom widget. **Confidence: high for the mechanism, medium for the density**, and what would change my mind is at the bottom.

**Run it.** `xvfb-run -a ./.venv/bin/python spikes/sourceview_decoration.py --report`, or without `--report` for a window you can click around in.

## What was tried

Three ways to put a full-width styled row between two lines of editable code, each on its own tab of the same window, each over the same 38-line sample.

### 1 · Child anchor — insert the row into the buffer

Insert a newline, create a `Gtk.TextChildAnchor` at it, and hang the widget there with `add_child_at_anchor`.

It looks right, and it is disqualified. **The anchor is a real character in the buffer**, so `get_text()` no longer matches the file on disk. The screenshot shows the tell: the verdict has its own line number, 17, and every line after it has shifted by one. The cursor walks into the row, select-all copies it, and saving writes it to the file.

FR-ED-07 forbids exactly this, and DD-9 says round-trip safety is a hard constraint. Nothing about this approach can be fixed, because the defect is the mechanism.

### 2 · Overlay — float the row over reserved space

Reserve space under the line with a `Gtk.TextTag` carrying `pixels-below-lines`, then place the widget in that gap with `add_overlay` in buffer coordinates.

**The buffer is untouched.** Round-trip is clean, the cursor steps from the anchored line straight to the next line of code, and copying takes no verdict text. Line numbers stay continuous. It scrolls with the text without a scroll handler, because `add_overlay` works in buffer coordinates.

### 3 · Gutter — a renderer in the margin

A `GtkSource.GutterRendererText` marking the line.

This works and it answers a different question. **A gutter cell is as wide as the gutter**, so it can carry a marker, a colour and a character. It can't carry *"Exposes rds.orders to the internet — 4 hops"*. Keep it for the marker in the margin that says a verdict exists; it isn't the verdict.

## What broke, and what it teaches

**The first working version was wrong in a way the measurements called clean.** All three checks passed for the overlay — round-trip clean, cursor out, copy clean — while the row was drawn on top of the `subnet_id` line beneath it. The reserved gap was 26px and the row was taller, and nothing compared the two.

The fix is that **the gap and the row are one number**, `VERDICT_HEIGHT`, used for both. Two numbers drift, and when they drift the row lands on a line of the user's code.

Worth carrying into the real editor as a rule: an annotation that reserves space must be sized from the same value that reserves it. And worth carrying into how this project is checked — the assertions were all true and the picture was broken, so **rendering it and looking isn't optional**.

Four toolkit errors on the way, all of them GTK3 memory. They are in `docs/toolkit-notes.md`.

## Recommendation

**GtkSourceView plus the overlay mechanism.** Approach 2 for the verdict band, approach 3 for the gutter marker beside it. Approach 1 is never used.

## What would change my mind

This tested **one** annotation on a 38-line file. Neither of the things that could still sink it was measured:

- **Density.** FR-ED-05 implies many verdicts at once. Every overlay is a widget, and repositioning them all on edit or resize is work proportional to their number. Fifty findings on a 5,000-line file against NFR-09's 300ms budget is the test, and it hasn't been run.
- **Interaction with plan highlighting.** Plan highlighting wants changed lines styled. Whether `pixels-below-lines` tags and line-background tags compose cleanly, or fight, is unknown.

Both are measurable and both belong in the performance corpus that R-11 says to build in P1 rather than P4. Neither blocks the first editor work.
