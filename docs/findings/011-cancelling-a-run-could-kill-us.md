# Cancelling a run could kill the process that started it

## The bug

`Run._stop` signalled a process group it looked up at kill time:

```python
os.killpg(os.getpgid(self._process.pid), send)
```

`os.getpgid(pid)` answers about **whatever holds that pid now**. A child that
has already been reaped leaves its pid free, the kernel reuses pids, and the
group that comes back can be anybody's — including this process's own. The next
line then sends `SIGTERM` and `SIGKILL` to it.

## How it showed

The test suite was being killed part-way through, at a different point each
time, roughly one run in three. `make check` reported `Error 137`, which is
SIGKILL, with no failure and no traceback — because nothing had failed. The
process was simply gone.

## What went wrong on the way

It was put down to memory, twice, and 674 MB against 8 GB free was only measured
after the second time. Then "windows were being closed by hand" was accepted as
the whole explanation, which was true of *some* of the kills — the app really
was putting dialogs on the desktop (finding 010) — and the search stopped. Two
causes with one symptom, and the first true one made the second invisible.

**A cause that explains the evidence is not the cause.** The evidence here was
"the process dies at a random point with no output", and at least three
different stories fit it.

## The fix

The group is read once, when the child is certainly alive, and never looked up
again. `start_new_session=True` makes the child a session leader, so its group
id is its pid at that moment. The whole group is still signalled, because
`tofu` spawns provider plugins and signalling only the parent leaves those
running.

`tests/engine/test_never_kills_us.py` asserts the group is recorded at spawn,
that a reaped run does not consult it again, that cancelling kills the child
and its plugins, and that we are still here afterwards.

## What is not proven

The suite has run cleanly many times since. Whether anything else can still
crash it is not established — one run in an earlier batch produced a
`faulthandler` dump that was never reproduced. It is not claimed fixed.
