# 004 — The activity log records which stack, so freshness can be computed

**Decided 2026-09-09.**

## What was chosen

`Happened` gains one field: `stack`, the name of the declared stack a plan or an
apply ran against, empty for a module nobody has grouped.

## Why a persisted shape was changed

**A stack is stale when something it depends on has been applied since this one
was last planned.** That is a question about two timestamps, and the activity
log is the only place either of them is kept. Keeping a second record of the
same events would be a second record that can disagree with the first.

The alternative was to write the stack name into the existing free-text
`detail`, which already carries *"2 of 6"* on an apply. Two meanings in one
field is how a field stops being parseable, and the parse would be a guess.

## Why this is safe to add

The log is JSON lines, and `read()` takes every field with a `.get(…, "")`
default. An entry written before today reads back with `stack=""` and is simply
not about a stack; an entry written today read by an older copy has one key it
ignores. **Nothing is rewritten and nothing is migrated.**

## What it is for

`engine/stacks/freshness.py`, and through it the verdict line's `data is stale ·
N waiting` chip — which is what replaced a resident Stacks section in the file
rail. That section cost four rows of permanent height and, on the ordinary day,
said nothing at all.

## What the engine layer may not do

`engine/stacks/` reaches nothing — a stack parses, validates and graphs entirely
offline, and `tests/architecture/test_layering.py` enforces it. So `freshness`
takes plain `Event(kind, stack, at)` records rather than importing the activity
log, and the window, which owns both, is what joins them.
