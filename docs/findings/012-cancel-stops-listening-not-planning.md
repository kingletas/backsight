# Cancel stops listening, it does not stop planning

## The bug

The footer offers `Cancel` as the primary action for the whole time a plan is
running, which is the right offer — a plan against a real account takes 20 to 90
seconds, and improvement.md organises most of the design around that wait.

It does not cancel the plan. `Speculator.cancel` bumps a generation counter, and
the generation check in `_begin`'s worker then discards the answer when it
arrives. The engine keeps running to completion.

The runner already has everything needed. `process.start` hands back a `Run`
with a `cancel` that signals the whole process group, waits, and escalates to
`SIGKILL` — the machinery finding `011` was written about. But `speculative`
starts and waits in one expression:

```python
written = process.start([engine, "plan", ...], cwd=directory, ...).wait()
```

The handle is never held, so nothing above it can reach the process.

## The measurement

The real runner and the real `Speculator`, with `sleep` where `tofu plan` goes —
the same shape as `speculative`: start, then wait.

```
plan process running: True
after cancel, still running: True
```

## Why it matters more than a wasted process

`tofu plan` holds the state lock. A cancelled plan that keeps running keeps the
lock, so the next plan queues behind a run nobody is waiting for any more, and a
colleague running Terraform against the same workspace is blocked by a plan this
person cancelled. improvement.md §6 is about exactly this: the lock is the
normal condition rather than an error, and the tool should be honest about who
holds it.

It is also a claim that is not true. The button says Cancel, the status says
cancelled, and the work continues.

## Fixed

`speculative` takes a `started` callback and hands its `Run` to it before
waiting. The `Speculator` holds that for as long as one is in flight and
cancels it before bumping the generation, outside the lock — killing a process
group waits on it, and holding the lock through that would block the next save.

Measured the same way it was found:

```
plan process running: True
after cancel, still running: False (0.50s)
```

`is_worth_reporting` is deleted. The generation check already stops a cancelled
run from being reported, so it was a guard nothing called.

## The shape of the fix

`speculative` takes a way to hand its `Run` back — a callback, or returning the
handle before waiting on it — and the `Speculator` holds it for as long as one
is in flight. `cancel` then cancels the run before bumping the generation.

`is_worth_reporting` in `speculation.py` is dead code from the version of this
that reported cancellations: nothing calls it, because the generation check
already stops a cancelled run from being reported. It stays dead or it becomes
the guard again, depending on which end does the cancelling.
