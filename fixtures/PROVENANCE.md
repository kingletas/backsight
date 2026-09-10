# Provenance

Every fixture here is real output from a real tool. Nothing in this directory was written by hand or inferred from a remembered shape. The one edit is noted where it was made.

Captured 2026-09-06 on Ubuntu 24.04 with **OpenTofu v1.12.6**.

## `schema/providers-schema.json.gz`

`tofu providers schema -json`, gzipped from 13 MB. Providers pinned in the capture workspace: `hashicorp/aws 5.82.2`, `hashicorp/null 3.2.3`, `hashicorp/random 3.6.3`, `hashicorp/local 2.5.2`, from `registry.opentofu.org`. The AWS entry alone carries 1,470 resources and 593 data sources.

**Read this before writing anything that depends on the schema.** Across the entire file the only attribute keys that exist are `computed`, `deprecated`, `description`, `description_kind`, `optional`, `required`, `sensitive` and `type`. There is **no force-replacement field**, and no description says "forces new resource". See `docs/findings/001-force-replacement-is-not-in-the-schema.md`.

## `schema/random-3.5.1.json` and `schema/random-3.6.3.json`

The same command against `hashicorp/random` at two versions, captured so version-pinned resolution is tested against a real difference rather than a manufactured one.

**`random_bytes` exists in 3.6.3 and not in 3.5.1.** That is the whole test: a workspace whose lock file pins 3.5.1 must never be offered it.

## `plan/*.json`

`tofu show -json <plan>` against a workspace using only the built-in `terraform_data` resource, so the capture needs no provider, no credentials and no network.

| File | What it holds |
|---|---|
| `create.json` | one resource, `actions: ["create"]` |
| `update.json` | the same resource changed in place, `actions: ["update"]` |
| `replace.json` | `actions: ["delete","create"]`, `action_reason: "replace_because_cannot_update"`, `replace_paths: [["triggers_replace"]]` |
| `destroy.json` | `tofu plan -destroy`, `actions: ["delete"]` |
| `moved.json` | a rename carrying a `moved` block — `actions: ["no-op"]` |
| `rename-unsafe.json` | the same rename without the `moved` block — `delete` plus `create` |

The last two are a matched pair, and they are the ground truth the whole refactoring milestone is built on. One is what a rename must look like; the other is what it must never be allowed to do.

## Not captured, and why

- **`lsp/initialize.json`** — `terraform-ls` is not installed on this machine; the binary on `PATH` is a placeholder that says so. The LSP client is outside the agreed MVP, so this is deferred rather than blocked. Capture it before starting on the client.
- **`ministack/`** — the emulator is outside the agreed MVP, so nothing here is captured against it yet. **It does exist**: `ministackorg/ministack`, MIT licensed, on PyPI and Docker Hub, so BRD DD-4's claims hold and the sandbox work is not blocked on the question. Capture these before starting on it.

## `local-state/`

`terraform.tfstate` produced by `tofu init && tofu apply -auto-approve` against
the `plannable` module — the engine's own `terraform_data` resource, so no
provider, no credentials and no network were involved and every value in it is
invented. OpenTofu 1.12.6, 2026-09-07.

## `plan-failures/`

`quoted-type-constraint.out`, `missing-required-argument.out` and
`unsupported-argument.out` are `tofu validate -no-color` against a module
written to produce exactly that one diagnostic. OpenTofu 1.12.6, 2026-09-07.

A fourth was attempted and is deliberately absent: OpenTofu 1.12 no longer
emits the interpolation-only deprecation warning, so there is no capture of it
and no rule keyed on it.

## `example/`

The demo workspace. `terraform.tfstate` is a real `tofu apply` of an earlier
version of `main.tf`, so the shipped configuration differs from the shipped
state and the first plan contains an add, a change, a replace and a destroy.
Built on `terraform_data`, the engine's own resource, so it needs no provider,
no credentials and no network — every id and value in it is invented by the
engine. OpenTofu 1.12.6, 2026-09-07.

## `fmt/`

`unformatted.tf` written by hand, `formatted.tf` its output through
`tofu fmt -`, and `broken.out` what `fmt -` says about a file that will not
parse. OpenTofu 1.12.6, 2026-09-07.


## `apply/`

Real `tofu apply -json` streams, both of them from a run that actually happened.

`succeeded.jsonl` is the example workspace applied against its own shipped
state, so it carries all four kinds of change — a create, an update, a replace
(destroy then create, arriving interleaved with the rest) and a delete — with
`after-succeeded.tfstate` as the state it left behind.

`failed-part-way.jsonl` is `failing-main.tf`: three resources in a dependency
chain where the second has a `local-exec` provisioner that exits 3. The first
resource is created and stays created, the second errors, and the third is
never reached. That is the partial-apply state the apply screen exists to
describe, and it cannot be written by hand convincingly — the interleaving and
the `apply_errored`/`provision_errored` pair are what the parser reads.

Both on `terraform_data`, so no provider, no credentials and no network, and
every id in them is invented by the engine. OpenTofu 1.12.6, 2026-09-07.

## `apply-fails/`

A workspace whose apply stops part way: three `terraform_data` resources in a
dependency chain, where the second has a `local-exec` provisioner that exits 3.
Applying it leaves the first created, the second errored and the third never
started. It is here so the partial-apply path can be exercised against a real
engine rather than only against the capture of one. OpenTofu 1.12.6, 2026-09-07.

## `drift/`

Real drift, which needs a resource with something behind it: `terraform_data`
keeps no reality outside its own state, so a refresh of it can never disagree
with anything. These use the `local` provider, whose resources are files on
disk — a file edited by hand and a file deleted are drift a person can cause in
a second and a provider genuinely reports.

`detected.jsonl` is `tofu plan -refresh-only -json` after one generated file was
edited outside Terraform and another was deleted; it carries the
`resource_drift` events the drift check reads. `refresh-only-plan.json` is the
same run's structured document, trimmed to `resource_drift`, which is where the
before-and-after attribute values live. `none.jsonl` is the same workspace after
reconciling, and carries no drift events at all — the quiet case, because a
check that has only ever been seen firing has not been tested.

OpenTofu 1.12.6 with `opentofu/local` 2.5, 2026-09-08.

## `registry/`

`opentofu-local-versions.json` is a real response from
`registry.opentofu.org/v1/providers/opentofu/local/versions`, trimmed to the
version strings and protocols — the platform lists are most of the bytes and
nothing reads them. Twenty-eight versions, newest first, which is the ordering
the check depends on and the reason a capture is worth more than a guess.

A request for a provider that does not exist answers `404`, which is why an
unknown provider is a silence rather than an error. Captured 2026-09-08.

## `docs/`

Real provider documentation, fetched from each provider's own repository at the
tag matching the version in the schema fixture. Two files because there are two
layouts and a reader written against one silently finds nothing for the other:

`aws-s3_bucket.html.markdown` is the legacy layout — `website/docs/r/<name>.html.markdown`,
which the AWS provider still uses. `local-file.md` is the modern one —
`docs/resources/<name>.md`, which is what a provider generated by
`tfplugindocs` produces, and what most providers now ship.

Both carry YAML front matter, a heading, prose, and `## Example Usage` with
fenced Terraform. The examples are the part worth having: they are the
provider's own, they are correct, and they are what somebody actually wants
when they open documentation.

A request for a resource that does not exist answers `404`, which is why an
unknown resource is a silence rather than an error.

terraform-provider-aws v5.82.2 and terraform-provider-local v2.5.2,
fetched 2026-09-08.

## `policy/`

Real `checkov -d . -o json` output, from `main.tf` in the same folder — a
bucket with nothing configured and a security group open to the world on port
22. Ten findings, each carrying `file_line_range`, which is what makes a
finding something the gutter can point at rather than a line in a report.
The capture directory's absolute path was replaced with `/tmp/policy-capture/`
in every `file_abs_path` and `definition_context_file_path`; nothing else changed.

`checkov-clean.json` is the same command against a workspace built on
`terraform_data`, which has nothing to find. It is the more important of the
two: a checker that has only ever been seen firing has not been tested, and the
clean shape is not the failing shape with an empty list in it.

Checkov 3.x, 2026-09-08. OPA and Trivy are not installed on this machine, so
there is no capture for either and nothing is written against them.

## `git/`

Real `git status --porcelain=v2 -b` from a repository put into each state by
hand: `status-mixed.txt` has a file staged, a file changed and not staged, and
an untracked file all at once, which is the ordinary state and the one where a
reader that treats the two-character code as one thing gets it wrong.
`status-clean-ish.txt` is the same repository with only an untracked file left.

`push-no-remote.txt` is what `git push` says with nothing configured, because
that is the state of every repository somebody starts here and it must read as
a state rather than as a crash.

git 2.x, 2026-09-08.

## `library/`

**Invented, and that is the point.** Nothing was captured to make it — there is
no external interface here, only a workspace shaped the way a real module
library is shaped, so that rules about *twenty-something of something* have
somewhere to fail.

Every rule it exercises broke when the application was driven against a real
repository and passed against the fixtures that already existed, because those
are four to ten files in one or two modules:

- **Two groups of root modules**, `examples/` and `modules/`, which share no
  prefix between them — a single shared prefix over all of them is the empty
  string.
- **Root modules beside library modules under one folder**, so the two have to
  be told apart by something other than where they live.
- **No backend anywhere**, so a warning about local state is true of every row
  and distinguishes none of them.
- **Enough files that expanding every module fills the rail** before the top of
  the tree has been read.

Two of the examples carry a `.terraform.lock.hcl`, shaped after the real one in
`workspace/environments/prod/` and with invented versions. They lock `random`
at the same version from **two different registries**, which is the pair that
printed itself twice in the verdict line's provider list.

Nothing here plans: there is no provider to plan against and no credentials to
plan with. It is a workspace to look at.
