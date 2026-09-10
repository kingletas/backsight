# A palette check fails intermittently and has never reproduced

## What is seen

One of the palette checks in `scripts/gui-smoke.py` fails roughly once in ten
runs of the whole smoke. The failing check varies: it has been
`@terraform_data` alone, and on one run `@api`, `main` and `:12` together while
`@terraform_data` and `>plan` passed.

## What has been ruled out

**The palette itself.** A probe that opens the palette forty times and runs
four queries against each — 160 in total, in a clean process — is clean every
time.

**The entries being wrong.** They are built from `Workspace.modules`, whose
files are sorted, and from `SourceMap.places`, which is insertion-ordered over
those sorted files. Ranking is deterministic: `terraform_data.api` scores above
`terraform_data.worker` because it is shorter.

**A partially written file.** `Document.write` was not atomic and now is —
finding `008` — and the flake outlived that fix, so it is not the cause.

## What is known about when

It appears only inside the full smoke, and most often when several `xvfb-run`
processes are competing. That points at timing rather than logic, but the
assertions read Python state that `set_text` fills synchronously, so how load
reaches them is not understood.

The one run with three consecutive failures is the informative one: `:12`
cannot fail from missing entries, because `Line 12` is generated rather than
matched. That check failing means **`refresh()` did not run for that
`set_text`**, and the previous query's results were still on screen.

## What has been done

Nothing has been changed to "fix" it, because nothing is known to be wrong.
Every palette check in the smoke now prints the query, the entry's text, what
was shown and what the entries held, so the next occurrence says what happened
rather than only that something did.

**This is an open defect, not a resolved one.**
