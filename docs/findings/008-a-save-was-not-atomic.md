# A save truncated the file before filling it

`Document.write` was `Path(...).write_bytes(data)`, which opens the file with
`O_TRUNC` and then writes. Between those two moments the file is empty or
partial on disk.

## Why it matters here more than in most editors

Everything in this application reads these files while they are being edited:
the source map builds resource addresses from them, the palette lists those
addresses, the run marks read test files, the change map and the gutter read
the plan against them. Several of those run on background threads.

A reader landing in that window sees an empty file, parses it, and reports a
workspace with **no resources in it** — confidently, with no error anywhere.

A crash or a power loss in that window leaves **the person's own source file
truncated**, which is worse than any of the above.

## How it surfaced

A smoke check on the command palette — that `@terraform_data` finds the two
resources in the fixture — failed twice in about twenty runs and could not be
reproduced deliberately. Eight consecutive runs afterwards were clean. It was
not chased to a conclusion; looking at what the smoke does around that point
found a save on one thread and a file read on another, and the write turned out
not to be atomic.

**The flake is not proven to be this.** What is proven is that the write was
not atomic, that a concurrent reader could see a partial file, and that it is
now atomic and cannot.

## What it is now

A temporary file in the same directory, `fsync`, then `os.replace` — atomic
within one filesystem, which is why the temporary cannot go in `/tmp`. An
existing file keeps its permissions, because they may have been set
deliberately and a save is not the place to change them.

`tests/text/test_atomic_write.py` reads the file continuously from another
thread while it is rewritten a hundred times and asserts that every read is one
whole version or the other. It was checked in the failing direction: against
the old write it reports a partial file at once.
