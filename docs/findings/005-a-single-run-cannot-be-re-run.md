# A single `run` block cannot be re-run on its own

Checked against OpenTofu 1.12.6. `tofu test` takes one filter and it is
file-level:

```
-filter=testfile      If specified, OpenTofu will only execute the test files
                      specified by this flag.
```

There is no flag that names a run block. Runs inside a file execute in order
and the file is the smallest unit the engine will accept.

## What this changes

Sheet 7 asks for a gutter mark on each `run` block, clickable to re-run. The
mark is fine — the shape and the last result belong to the run. **The click
cannot mean what it looks like it means.** Clicking the mark beside
`names_are_wrong_on_purpose` runs the whole of `nodes.tftest.hcl`, including
every run before it, and in a file where an earlier run applies real
infrastructure that is not a small difference.

So the tooltip says which file will run and how many runs are in it, rather
than naming the one beside the cursor. A control that quietly does more than
its label says is the defect this product exists to prevent, and it would be
absurd to ship one in the gutter.

## What it does not change

Marks still come from the run, not the file: each run keeps its own shape and
its own last result, because that is what a person reads the gutter for.
