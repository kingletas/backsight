# The console stops at the first error, and redacts on its own

Measured against OpenTofu 1.12.6, in `fixtures/plannable` and a scratch module.
Captured output is in `fixtures/console/`.

## It is not a batch evaluator

Four expressions piped into one `tofu console` produce two results and then
nothing. The third was `var.nope`, which is undeclared; the console printed the
error, exited 1, and never read the fourth line.

```
1 + 1              -> 2
terraform_data.api -> (known after apply)
var.nope           -> Error: Reference to undeclared input variable
length([1,2,3])    -> never evaluated
```

So a session can't be one long-lived process that survives a typo, which is
what a REPL usually is. **One process per expression** is the only shape that
gives an answer per expression. It costs about 47ms, measured, which is cheap
enough that this is a design choice rather than a compromise.

The consequence for the panel: history is ours to keep, because the engine
keeps none.

## Results go to stdout, errors to stderr, both coloured

ANSI escapes appear even when stdout is a pipe, so `-no-color` isn't optional.
The error carries a location — `on <console-input> line 1` — which is always
line 1 of what the person just typed, and is therefore noise. Strip it.

## An unapplied resource evaluates to `(known after apply)`

`terraform_data.api` in a workspace that has never been applied returns
`(known after apply)`, not its configuration. The console reads state, so
before an apply there is very little in it. Say this in the panel rather than
letting someone conclude their expression is wrong.

## Sensitive values are redacted by the engine, and the taint propagates

A `sensitive = true` variable prints `(sensitive value)`, and it stays redacted
through every route tried:

| Expression | Result |
|---|---|
| `var.token` | `(sensitive value)` |
| `jsonencode(var.token)` | `(sensitive value)` |
| `substr(var.token, 0, 4)` | `(sensitive value)` |
| `split("-", var.token)` | `(sensitive value)` |
| `base64encode(var.token)` | `(sensitive value)` |
| `"prefix-${var.token}"` | `(sensitive value)` |
| `[var.token]` | `[ (sensitive value), ]` |
| `nonsensitive(var.token)` | the value |

`nonsensitive()` is the documented opt-out and it is typed by hand, by the
person, in their own console. That is the right boundary and we don't close it.

**We add no redaction pass of our own.** A second redactor would be a copy of a
rule we don't own, and it couldn't tell the literal string `(sensitive value)`
from a redaction. What we do instead is never write console output to a log or
a file — FR-DBG-06 is upheld by not making a copy.
