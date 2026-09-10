# Finding 003 — the test framework's missing values are already in the JSON

**Good news, and it makes sheet 7 much cheaper than it assumes.**

## What sheet 7 says

> Terraform's test framework has existed since 1.6 and adoption is poor. The reason is not that engineers dislike testing infrastructure — it's that mocks prove little, real runs cost money, and **a failure prints "assertion failed" with no values**.

FR-TST-03 makes fixing that a mandatory requirement, and calls it *"the reason people abandon the test framework"*.

## What is actually true

That is true of the **human-readable** output and false of `-json`. A failing assertion already carries the evaluated value of every expression the condition referenced:

```json
"snippet": {
  "code": "    condition     = length(terraform_data.nodes) == 5",
  "values": [
    {"traversal": "terraform_data.nodes", "statement": "is tuple with 3 elements"}
  ]
}
```

Captured from `tofu test -json` against `fixtures/tests/workspace`, and committed as `fixtures/tests/run-with-a-failure.jsonl`.

**So FR-TST-03 is a presentation problem rather than a data one.** The differentiator sheet 7 builds its case on costs a reader and a panel, not an evaluator. That is a large reduction: the alternative would have meant evaluating HCL expressions ourselves against plan state, which is most of a language runtime.

## The trap that came with it

> [!danger]
> **A plan file contains sensitive values in plain text.**
>
> ```json
> "after":           {"input": "hunter2"},
> "after_sensitive": {"input": true}
> ```
>
> Anything that displays a planned value and forgets to consult the second key leaks the first. FR-DBG-06 says sensitive values are never revealed and no setting turns that off — so it is enforced by the type: a `Resolved` for a sensitive attribute holds its value privately and `display` refuses. There is no accessor that returns it, and a test asserts no public attribute renders the secret.

## What this changes

| | Before | After |
|---|---|---|
| FR-TST-03 | Assumed to need our own expression evaluator | A reader over the engine's JSON |
| Sequencing | Sheet 7 argues it should follow convergence | Still right, and cheaper than argued |
| FR-DBG-01 | A console evaluating arbitrary expressions | Still ours. `tofu console` exists and is a separate integration |

**Sheet 7's sequencing argument stands and gets stronger.** The test runner is mostly a view over machinery that already exists.
