# Backsight

[![check](https://github.com/kingletas/backsight/actions/workflows/check.yml/badge.svg)](https://github.com/kingletas/backsight/actions/workflows/check.yml)
[![licence: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

A Terraform workbench for Linux that shows what a change will do while you write
it. GTK 4 and libadwaita, Python, no browser engine.

> [!warning] Early, and not released
> Version `0.0.0`. Nothing has been tagged, the interface still moves, and the
> first version will be cut when the editor is usable for a day's work without
> surprises. Read it as something being built in the open, not something to
> depend on.

## What it is for

Writing Terraform has no feedback loop shorter than a full CI run. You cannot
see what your code will do, what it will cost, or what it exposes, until after
commit, push and wait.

The sharpest case: renaming a resource is a production outage waiting to happen.
You see a rename. Terraform sees a destroy and a create. Nothing in a
general-purpose editor warns you.

Backsight puts that feedback beside the file you are typing in.

## What works today

- **A plan beside your code**, run as you save or on demand, with what would be
  created, changed and destroyed — and what forces a replacement.
- **Apply**, shown happening: the same resources in the order you reviewed them.
  Three endings, not two — applied, stopped part way, and nothing changed. The
  state is read back afterwards and checked against what the plan intended.
- **Drift** — what changed outside Terraform, from a refresh-only plan.
- **A library of reusable Terraform** — snippets, examples, recipes and runbooks.
  `Ctrl+E` finds one, Return puts it in the file with the first field selected.
  Twelve ship, plus one generated per resource type from the provider schema.
- **Provider documentation**, mirrored from each provider's own repository and
  matched to the version in your lock file, with its examples insertable.
- **Policy findings** from whichever scanner is on `PATH`, on the line that
  caused them. Nothing is enforced.
- **What a change costs**, with usage-priced resources marked as not estimable
  rather than reported as zero. No prices ship.
- **Extract to a module**, with the `moved` blocks that stop it being a destroy.
- **Git** — staging per file, commit, branches, and push behind a question.
- **Credentials discovered without ever holding one**, and a separate profile
  for reading and for applying.

## What it deliberately does not do

**Multiple cursors, column selection, code folding and indent guides are not
built.** GtkSourceView 5 has no API for any of them, and building the first
three means reimplementing every editing path — which puts at risk the two
things this editor promises hardest: that it never rewrites a file it was not
asked to, and that what you saved is byte for byte what you typed.

Anybody arriving from VS Code will notice, so **the keys answer rather than
going quiet**: `Ctrl+D` selects the next occurrence and says once what it cannot
do and what to use instead, every blocked menu item carries its own reason, and
**Help → What Backsight will not do** lists all four limits, the four things
this refuses on purpose, and the three that are simply not built yet. The
reasoning is in [`docs/findings/002`](docs/findings/002-three-baseline-capabilities-have-no-api.md)
and [`016`](docs/findings/016-indent-guides-have-no-api-either.md).

**No credential is ever stored, shown or logged**, and there is no setting to
turn that off.

## Not built yet

Sign-in through IAM Identity Center, surfacing a held state lock, and generating
`import` blocks. Each is waiting on something real rather than on time — an
Identity Center to capture against, a lock that can be held, and an id format
the provider schema does not carry.

## Running it

You need OpenTofu or Terraform on your `PATH`, the GTK 4 bindings, and
[`uv`](https://docs.astral.sh/uv/getting-started/installation/), which builds
the environment it runs in.

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gtksource-5
```

The two typefaces it is drawn in. Without them it falls back to whatever the
desktop has, which is a design nobody chose — Preferences says so when that
happens rather than leaving you to wonder.

```bash
sudo apt install fonts-ibm-plex fonts-jetbrains-mono
```

```bash
git clone https://github.com/kingletas/backsight && cd backsight && make app
```

[`docs/from-nothing.md`](docs/from-nothing.md) walks through a first plan, on an
example that needs no provider and no credentials. `make` on its own lists
everything else. `make check` is what a commit has to
pass, and it is the same thing CI runs.

## How it is put together

The engine knows nothing about the toolkit — `src/backsight/engine/` may not
import `gi`, and a test enforces that. Everything on screen is in
`src/backsight/app/`. A findings document in [`docs/findings/`](docs/findings/)
records each investigation that changed the design, including the ones where
the answer was that a thing could not be done.

- [CONTRIBUTING.md](CONTRIBUTING.md) — the shape a change should arrive in
- [SECURITY.md](SECURITY.md) — the model, and where to report something
- [CHANGELOG.md](CHANGELOG.md) — what changed
- [docs/BRD.md](docs/BRD.md) — what it is meant to become
- [docs/why.md](docs/why.md) — the problem it was built for, and what that decided
- [docs/design-conformance.md](docs/design-conformance.md) — what the design asks for, what is built, and how to build the rest

## Licence

MIT. See [LICENSE](LICENSE).
