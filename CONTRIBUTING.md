# Contributing

Thanks for looking.

## The gate

```bash
make check
```

That's everything a commit has to pass, and it's what the pre-commit hook runs.

## What a change should look like

- One concern per pull request, with the reasoning in the description.
- `make check` green.
- A test that fails before your change and passes after it. **One direction
  isn't a test**: something that fires isn't evidence it can be quiet, and
  something quiet isn't evidence it can fire.
- An entry in `CHANGELOG.md` under a new heading, saying what changed for
  somebody using this rather than what the diff did.
- Comments say what the code does or what it guards against, in a sentence or
  two. History belongs in the commit message and the changelog.

## Fixtures come from the real tool

Don't write code against an external interface until a real response from it
is committed under `fixtures/`. That covers `tofu` and `terraform` output, the
provider schema, `terraform-ls`, MiniStack and AWS responses. Run the real
thing, commit the raw output with where it came from in `fixtures/PROVENANCE.md`,
then write the code and the test against it. A guessed JSON key is the cheapest
way to lose a week.

## Architecture rules

A test in `tests/architecture/` fails the build on these:

- **`engine/` never imports `gi`**, so everything except the window runs and
  tests without a display (`test_layering.py`).
- **A file is never rewritten beyond what was asked**: no reformatting,
  reordering or normalising on save (`test_round_trip.py`).
- **Nothing names the machine it was written on**: no home paths, logins,
  per-user temp paths, real account numbers or credential shapes
  (`test_no_private_information.py`).

These are held by review, and a test for either is welcome:

- **The window never waits on a subprocess, a large read or the network.**
  Subprocesses start in `engine/runner/` and nowhere else.
- **No credential reaches a file, a log or a cache.** Credentials stay in
  memory or the system keyring.

Anything that generates `moved`, `import` or `removed` blocks, or touches a
state file, needs its acceptance test before the code.

## Security

Don't open a public issue for a vulnerability.
[SECURITY.md](SECURITY.md) has the reporting route.
