# The integration environment

**A disposable emulator, and every engine command this application runs, driven
against it.**

The application already talks to the engine. Nothing here reimplements that —
every test calls the function the application calls, so a defect in argument
construction, working directory, environment, process lifetime, exit-code
handling or output parsing fails here rather than being stepped over. The engine
CLI and the emulator's own API appear only as **setup and verification**: after
the application has done something, they go and ask whether it happened.

## Running it

```bash
make integration
```

That is `infra-test/scripts/test`: it starts the emulator, waits for it to say
it is ready, runs the suite, prints the container logs if anything failed, and
takes the stack down **on every ending** — success, an assertion, a crash, a
timeout or a Ctrl-C.

To keep it up and poke at it:

```bash
infra-test/scripts/up
```

```bash
KEEP_UP=1 infra-test/scripts/test -k apply
```

```bash
infra-test/scripts/down
```

`scripts/reset` empties the emulator without restarting it, which is what runs
between cases. `scripts/wait` is the health check on its own.

## What you need

**Docker or Podman, and `tofu` on your PATH.** Nothing else, and **no cloud
account** — the whole point of the emulator is that no test here can reach one.
With either missing the suite skips with a sentence saying what to install,
rather than failing fifteen times with a file-not-found.

Copy `.env.example` to `.env` to change the port or the emulator build. Every
value has a default, so a clean checkout needs no file at all.

## Two things it will not do

**It does not take port 4566.** The shared `dev-services` stack runs an emulator
of its own there, that emulator belongs to whoever started it, and a suite that
resets somebody else's emulator between cases is a suite that deletes their
work. This one is on **14566**, in its own compose project, under its own
container name.

**It does not persist.** `PERSISTENCE=0`, a tmpfs, and `down` takes the volumes
with it — because a test that passes because of what the last run left behind is
worse than a slow suite.

## Determinism

| What | Pinned by |
|---|---|
| The emulator | `MINISTACK_VERSION`, default `1.5.8`, in `docker-compose.yml` |
| The provider | `required_providers` in each fixture, plus the lock file `init` writes |
| The engine | `BACKSIGHT_ENGINE`, default `tofu`; CI installs a named version |
| The download | one `TF_PLUGIN_CACHE_DIR` for the whole run, `local.d/plugin-cache` by default, so nothing is fetched twice |

## The services, and why these

**Chosen from what the application's own fixtures already exercise**, not to
raise a number. Across `fixtures/`, the AWS resources that appear are S3
buckets, SQS queues, DynamoDB tables, VPC objects and a caller identity; the
rest are `terraform_data`, `null_resource`, `random_*` and `local_file`, which
need no service at all.

So: **`s3`, `sqs`, `dynamodb`, `sts`, `iam`**. Each is cheap to create and each
can be asked afterwards whether the object is really there — which is the whole
reason for an emulator rather than a mock.

## The commands this application runs

Discovered rather than listed: `backsight.engine.runner.invocations` walks the
package and reports every argument list handed to the engine, and a test fails
the build if the matrix below does not cover all of them.

| Invocation | Where |
|---|---|
| `<engine> apply -json -input=false -auto-approve <value>` | `backsight/engine/plan/applying.py:331` |
| `<engine> apply -no-color -input=false -auto-approve` | `backsight/engine/sandbox/convergence.py:145` |
| `<engine> console -no-color` | `backsight/engine/console/evaluation.py:89` |
| `<engine> fmt -check -diff -no-color` | `backsight/engine/plan/commands.py:107` |
| `<engine> fmt -no-color -` | `backsight/engine/plan/commands.py:153` |
| `<engine> init -no-color -input=false` | `backsight/engine/plan/commands.py:122` |
| `<engine> init -no-color -input=false` | `backsight/engine/sandbox/convergence.py:133` |
| `<engine> plan -refresh-only -input=false -out <value>` | `backsight/engine/plan/drifting.py:206` |
| `<engine> plan -no-color -input=false -out <value>` | `backsight/engine/plan/execution.py:108` |
| `<engine> show -json` | `backsight/engine/plan/commands.py:209` |
| `<engine> show -json <value>` | `backsight/engine/plan/drifting.py:218` |
| `<engine> show -json <value>` | `backsight/engine/plan/execution.py:120` |
| `<engine> test -json -no-color` | `backsight/engine/tests/execution.py:113` |
| `<engine> validate -json` | `backsight/engine/plan/commands.py:89` |
| `<engine> version -json` | `backsight/app/window.py:5908` |

## The matrix

| Command | Invoked by | Fixture | Emulator service | Expected | Verified by |
|---|---|---|---|---|---|
| `init` | `plan.commands.initialise` | base | — | the provider is installed and a lock file is written | `.terraform/` and `.terraform.lock.hcl` on disk |
| `validate` | `plan.commands.validate` | base, invalid | — | sound passes; an unknown argument and a dangling reference do not | `Validation.valid`, and every problem carries a line |
| `fmt` | `plan.commands.formatting, plan.commands.format_text` | base, unformatted | — | `-check` names the file and rewrites nothing; stdin returns the tidied text | the file's bytes before and after, and the returned text |
| `plan` | `plan.execution.speculative` | base, invalid | s3, sqs, dynamodb, sts | three creates, an artifact on disk, and nothing to do on a second run | `Plan.effective` and the artifact file |
| `apply` | `plan.applying.run` | base | s3, sqs, dynamodb | the objects exist; an update reaches the service; a destroy removes them | **the emulator's own API** — list_buckets, list_queues, list_tables |
| `show` | `plan.commands.state, plan.execution.speculative, plan.drifting.check` | base, outputs | s3, sqs, dynamodb | state names what was created; outputs come back with their types | `State.resources`, and the parsed `values.outputs` |
| `plan -refresh-only` | `plan.drifting.check` | base, outputs | sqs | a change made through the API is found; an untouched workspace is quiet | `Drift.resources`, after the queue is changed through SQS itself |
| `console` | `console.evaluation.evaluate` | outputs | — | an expression evaluates; an unknown reference says what is wrong | `Evaluation.value` and `Evaluation.failure` |
| `test` | `tests.execution.run` | tests | — | a passing file passes; a failing file is reported as failing | `Results.passed`/`failed`, and the failure's own message |
| `version` | `app.window._engine_version` | base | — | the binary says which version it is | the JSON carries `terraform_version` |

## What it does **not** run, and why

A reader comparing this against Terraform's own command list needs to know these
are absent because the application does not run them — not because nobody got
round to testing them.

| Command | Why there is nothing to test |
|---|---|
| `destroy` | Destruction is applying a plan that destroys, which is the promise that what runs is what was reviewed. There is no separate destroy path to test, and the destroy case above goes through `apply`. |
| `force-unlock` | Never run. A held lock is surfaced so somebody can find out who holds it; breaking one from a desktop editor is not a decision this makes. |
| `graph` | Never run. The dependency picture this application draws is the stack graph, which it computes itself and offline. |
| `import` | Named in a menu and blocked: the id format is not in the provider schema. |
| `login` | Never run, and never will be. No credential is stored, shown or logged, and there is no setting to change that. |
| `output` | Outputs are read out of `show -json`, which the application already runs for state — so there is no separate `output` invocation to test. |
| `providers` | The provider schema is read from a committed `providers schema -json` capture rather than by running the command. |
| `refresh` | Done as `plan -refresh-only`, deliberately: that is read-only, and `refresh` writes the state file. A drift check must not change anything. |
| `state` | State is read the same way, through `show -json`. Nothing here mutates state: `state mv` and `state rm` rewrite what exists without touching the infrastructure, which is the sharpest edge in the whole tool. |
| `taint` | Never run. It is superseded by `-replace` on a plan, and the application has no path that asks for either. |
| `workspace` | Named workspaces are not a concept this application exposes anywhere — it works on root modules and stacks, and there is no command, menu item or setting that reaches `workspace select`. |

## Fixtures

| Directory | For |
|---|---|
| `terraform/base/` | the happy path: one S3 bucket, one SQS queue, one DynamoDB table |
| `terraform/unformatted/` | deliberately not formatted, so `fmt -check` has something to refuse |
| `terraform/invalid/` | an argument the schema does not have, and a reference to nothing |
| `terraform/unreachable/` | a provider that does not exist, so `init` has something real to fail on |
| `terraform/outputs/` | `terraform_data` and four outputs — no provider, no credentials, no network |
| `terraform/tests/` | one `.tftest.hcl` that passes and one that deliberately does not |

**Everything in them is invented.**

## One thing the emulator does that is worth knowing

The AWS provider reports **`tags: null → {}`** on every resource it reads back
from this emulator, so a refresh over untouched AWS infrastructure here is never
empty. That is the provider and the emulator disagreeing about an unset map
rather than the application finding drift — so the *quiet* drift case runs
against `terraform_data`, and there is a test that names the tag behaviour so
the next person meets it as a known thing rather than as a mystery.
