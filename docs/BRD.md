# Business Requirements Document
## Backsight — A Terraform Workbench for Linux

| Field | Value |
|---|---|
| Document status | Draft v0.5 — for review |
| Date | 6 September 2026 |
| Supersedes | v0.4, v0.3, v0.2, v0.1 |
| Product working title | Backsight |
| Form factor | Desktop application (Ubuntu/Linux), GTK4 + Python |
| Reviewers required | Engineering, Security, Legal, Product |

**Changes from v0.4:** Stacks and dependencies added as a first-class capability (§6.11) with a corresponding delivery phase, design decisions DD-13 to DD-15, and orchestrated multi-stack apply deferred to §12. Candidate capabilities not adopted into this document are tracked separately in `docs/CANDIDATES.md`.

**Changes from v0.3:** Form factor changed from self-hosted server to desktop application. Team governance capabilities deferred to a v2 companion service (§12). Credential model changed to AWS IAM Identity Center. Technical constraints added (§9). Phasing reordered so the authoring workbench is first.

---

## 1. Executive Summary

Backsight is a desktop application for engineers who write Terraform. It is not an editor plugin, not a web console, and not a wrapper that shells out to `terraform` behind a form. It is a purpose-built workbench that knows the language, the provider schemas, the current state, the target account, the cost model and the security consequences of what is being written — and makes all of that visible while the engineer types.

The experience: open a workspace, scaffold a resource from an approved module, and write HCL in an editor that completes real subnet IDs from your account, marks which attributes will force a replacement, annotates instance types with their monthly cost, and shows the plan diff updating beside your code. Rename a resource and it generates the `moved` block so the rename doesn't destroy anything. Add a security group rule and it tells you, on that line, that you've just opened a four-hop path from the internet to a database. Run the whole thing against a local MiniStack container to prove it actually converges. Then apply — as yourself, via SSO, with no stored credentials anywhere.

It ships as a `.deb`. It starts in under two seconds. It has no browser engine, no JVM and no bundled runtime beyond Python. It works on a plane.

**v1 is a personal tool with advisory governance.** The team control plane — approvals that count as evidence, tamper-evident audit, enforcement that cannot be bypassed, scheduled drift detection, organisation-wide DORA metrics — requires a service that is not a laptop, and is specified in §12 as a v2 companion. The desktop application is designed from the start to attach to it without rework, and to remain fully functional without it.

---

## 2. Problem Statement

### 2.1 Authoring is blind

An engineer writing Terraform has no feedback loop shorter than a full CI run. They cannot see what their code will do, what it will cost, whether it passes policy, or whether it exposes something — until after commit, push, PR and wait. The result is a slow guess-and-check loop and code shaped by copy-paste from whatever module was nearest.

The sharpest case: renaming a resource in a text editor is a production outage. The engineer sees a rename; Terraform sees a destroy and a create. Nothing in a general-purpose editor warns them.

### 2.2 The tooling does not know the language

VS Code with the Terraform extension gives syntax highlighting and schema completion, and stops there. It does not know your account, so it cannot complete a real subnet ID. It does not know your policy, so it will happily suggest an instance type your organisation forbids. It does not know your costs, your state, your module catalog, or what your change will expose. Every one of those is knowable, and none of it is surfaced at the moment it would change what the engineer types.

### 2.3 Security scanning answers the wrong question

The question is "does this let anyone on the internet reach our database". Scanners answer "is this rule 0.0.0.0/0". They evaluate resources in isolation, so they miss exposure emerging from the combination of a security group, a subnet, a route table and a gateway — especially when some of those already exist and are not in the diff.

### 2.4 Failure surfaces at apply time

Configurations that pass `validate` and `plan` still fail during apply — dependency ordering, semantically invalid IAM documents, `for_each` expansion against real data. The blast radius is a half-applied state file.

### 2.5 There is no golden path

Approved internal modules exist but are undiscoverable, so engineers copy from whatever they find. The compliant way to build something is slower than the non-compliant way, and behaves accordingly.

---

## 3. Goals and Non-Goals

### 3.1 Goals

- **G1** — Reduce the authoring feedback loop from tens of minutes to seconds.
- **G2** — Make the consequences of a change — plan, cost, policy, exposure, replacement — visible at the moment of writing.
- **G3** — Make destructive refactors impossible to perform accidentally.
- **G4** — Catch convergence failures locally, before any code leaves the machine.
- **G5** — Answer exposure questions transitively, with verifiable evidence.
- **G6** — Make the golden path the fastest path.
- **G7** — Eliminate stored cloud credentials from the developer workstation.
- **G8** — Ship something lean: fast to start, small in memory, usable offline, installable in one command.
- **G9** — Build so that the v2 team service attaches without rework.

### 3.2 Non-Goals (v1)

- **NG1** — **Not a team deployment gate in v1.** Governance is advisory. Enforcement requires the v2 service (§12).
- **NG2** — Not a SaaS product, and not a web application.
- **NG3** — Not multi-cloud. AWS only.
- **NG4** — Not a public module registry.
- **NG5** — Not a CMDB or infrastructure inventory.
- **NG6** — Not a replacement for CI.
- **NG7** — No AI code generation. Guided authoring is deterministic, schema-driven scaffolding.
- **NG8** — Not cross-platform in v1. Linux only; Ubuntu is the reference target.
- **NG9** — Not an engine-agnostic platform in v1. Terraform and OpenTofu only (§5.1).

---

## 4. Users

| Persona | Description | Primary needs |
|---|---|---|
| **Infrastructure Author** (primary) | Writes Terraform daily or weekly. The v1 user. | Fast feedback, real completion, safe refactoring, not needing a browser tab open to the registry |
| **Occasional Author** | Application engineer who touches Terraform monthly. | Scaffolding, golden paths, guardrails that catch what they don't know to look for |
| **Platform Engineer** | Curates the module catalog and policy set. | Adoption of the golden path, a way to distribute conventions |
| **Security** (v2) | Consumes evidence, defines boundary and policy. | Deferred — requires §12 |
| **Engineering Leadership** (v2) | Throughput and reliability metrics. | Deferred — requires §12 |

### 4.1 Representative User Stories

- **US-1** As an Author, I type `subnet_id = ` and the editor completes the real subnet IDs in my account, labelled with their names and CIDRs.
- **US-2** As an Author, I hover an attribute and see that changing it forces replacement, before I change it.
- **US-3** As an Author, I change an instance type and see the plan diff and monthly cost delta update beside my code within seconds.
- **US-4** As an Author, I rename a resource and Backsight generates the `moved` block, then proves with a plan that nothing will be destroyed.
- **US-5** As an Author, I write a security group rule and the editor tells me on that line that it exposes an RDS instance to the internet, and shows the path hop by hop.
- **US-6** As an Occasional Author, I scaffold an S3 bucket from the approved module by filling a form, and get idiomatic HCL I then own.
- **US-7** As an Author, I run the whole change against a local emulator and prove it converges before I push anything.
- **US-8** As an Author, I apply as myself through SSO, and there are no credentials on my disk.
- **US-9** As an Author on a train with no connectivity, I can still edit, get full completion and hover documentation, and read provider docs.

---

## 5. Scope

### 5.1 Engine Support

**Terraform and OpenTofu only in v1.** The editor is the product, and an editor is language-specific. HCL tooling — terraform-ls, provider schemas, `moved` blocks, the plan format — is one integration serving Terraform, OpenTofu, and later Terragrunt and Terraspace. Pulumi and CDKTF are TypeScript/Python/Go: a different language server, a different scaffolding model, and a live-preview loop that requires compiling user code. That is a second product, not an increment.

| Phase | Engines | Authoring support |
|---|---|---|
| **v1** | Terraform, OpenTofu | Full |
| **v1.x** | Terragrunt, Terraspace | Full (shared HCL tooling) |
| **v2+** | CloudFormation, CDK, Pulumi, CDKTF, Helm, Ansible | Assessed after v1; each is a distinct execution model |

### 5.2 Cloud Scope

**AWS only.** Convergence testing depends on MiniStack, which emulates AWS. Exposure analysis (§6.6) is built on AWS network and IAM semantics. Value completion (§6.3) is built on AWS APIs. All three differentiators are AWS-specific.

### 5.3 Platform Scope

Ubuntu 24.04 LTS and 26.04 LTS as reference targets. Debian and Fedora on a best-effort basis. `.deb` at launch; Flatpak, Snap and AppImage follow (§9.5).

---

## 6. Functional Requirements

Priority: **M** = Must (v1), **S** = Should (v1 if capacity), **C** = Could (post-v1).

### 6.1 Application Shell and Workspace Management

| ID | Pri | Requirement |
|---|---|---|
| FR-APP-01 | M | Native GTK4 application following libadwaita conventions: adaptive layout, dark mode, system theme integration, standard keyboard shortcuts. |
| FR-APP-02 | M | Open a local directory as a workspace; detect root modules, backend configuration, provider requirements and lock file automatically. |
| FR-APP-03 | M | Clone from GitHub, and manage branches, commits, staging and push from within the application. |
| FR-APP-04 | M | Multiple workspaces open concurrently, with independent state, plan and credential context per workspace. |
| FR-APP-05 | M | Session restore — reopen workspaces, files, cursor positions and panel layout on launch. |
| FR-APP-06 | M | All long-running operations (init, plan, apply, convergence, schema indexing) run asynchronously without blocking the UI, with visible progress and cancellation. |
| FR-APP-07 | M | Offline mode is not a special mode. Every capability that can work without connectivity does, silently. |
| FR-APP-08 | M | **Command palette as the primary interface.** Every operation — plan, apply, convergence, refactor, scaffold, docs search, theme — is reachable by fuzzy search from a single keystroke. Chrome exists for the few actions that must be visible; everything else lives here. |
| FR-APP-11 | M | The palette opens with suggested and recent commands, never an empty prompt. Occasional users cannot search for a command they do not know exists, and this is the only affordance standing between them and a blank window. |
| FR-APP-12 | M | **Goto Anything over resource addresses.** Fuzzy navigation to any file, and to any resource, data source, variable, output or module across the workspace by its Terraform address. Resource addresses are the natural symbol table of an HCL project and are a better navigation model than the file tree. |
| FR-APP-13 | M | **Every panel is independently controllable.** The left rail, right rail, drawer, output and change map can each be shown, collapsed or hidden, with no dependency between them. Collapsed leaves a clickable strip; hidden removes the panel entirely and it is reachable only by key or menu. Default state on first run is the editor plus the status bar, with rails collapsed rather than hidden. |
| FR-APP-14 | M | Panel visibility, panel widths and pane splits are remembered per workspace and restored on reopen. Two workspaces may legitimately want different layouts, and a global layout forces one to be wrong. |
| FR-APP-15 | M | **Mouse parity.** Every command reachable by keyboard is also reachable by mouse — via the primary menu, a context menu, or a control in the interface. No capability may be keyboard-only. This is the discovery path for users who do not know a command exists, and it is what makes a palette-first tool viable for the Occasional Author. |
| FR-APP-16 | M | Context menus on the editor, the gutter, tabs, files in the rail, plan entries, change-map marks and status-bar segments, each offering the operations relevant to that object. |
| FR-APP-17 | M | Direct manipulation: tabs reorder by drag and tear out into a split; panel dividers drag to resize and double-click to collapse; the change map is clickable to scroll and hoverable to preview. |
| FR-APP-18 | M | Status-bar segments are controls, not labels. Clicking the plan summary opens the drawer; clicking the exposure count opens it scrolled to exposure; clicking the branch opens branch actions. |
| FR-APP-19 | M | **Open behaviour is configurable.** Single-click versus double-click to open a file, preview tabs on or off, whether a preview tab is promoted on edit or on double-click, where new tabs are inserted, and whether an already-open file is reused rather than opened twice. Ship a default and let people change all of it. |
| FR-APP-20 | M | **Preview tabs.** Single-click opens a file into a reused, visually distinct preview tab; editing it or double-clicking promotes it to a permanent tab. Single-click-to-open without this produces forty open files in a minute, so the two settings are coupled and the coupling must be explained where they are set. |
| FR-APP-21 | M | Tab behaviour settings: middle-click to close, confirm on closing unsaved, overflow as scroll or dropdown, maximum tab width, and whether closing the last tab in a pane closes the pane. |
| FR-APP-22 | M | **Settings are a file and a dialog.** A human-readable, version-controllable settings file is the source of truth; the preferences dialog edits that file. Anything settable in the dialog is settable in the file, and the file may be committed to share conventions across a team. |
| FR-APP-23 | M | **The menu specification is owned and declarative**, with named insertion points. Context menus are defined in one place, not accumulated by whatever code happens to append to them. Any future extension declares the section it belongs to. Duplicated and near-duplicated entries are a defect, not an inevitability. |
| FR-APP-24 | M | Context menus are contextual. A `.tf` file, a directory that is a root module, a directory that is not, and a non-Terraform file each get a different menu. Items that cannot apply are absent rather than disabled; items that could apply but are blocked are disabled with a reason. |
| FR-APP-25 | M | **A menu bar, hideable, with a primary menu as the fallback.** File, Edit, Selection, Find, View, Go, Terraform, Tools, Preferences, Help. Hiding it moves everything into a primary menu button so nothing becomes unreachable. |
| FR-APP-26 | M | **Settings precedence, in order: built-in defaults, then user settings, then workspace settings, then language-specific settings.** Each layer overrides the one before at the individual key. The preferences dialog shows which layer supplied the value in effect and offers to edit that layer. |
| FR-APP-27 | M | Key bindings and mouse bindings are user-editable files with the same precedence chain, and a "list bound keys" view resolves every binding in effect with its source. Conflicts are reported, never silently resolved by load order. |
| FR-APP-28 | S | Distraction-free mode and full screen, with their own settings layer so a user can have different rulers, wrap and panel state when writing versus reviewing. |
| FR-APP-29 | M | A console showing the application's own activity — subprocess invocations with their arguments, timings, and non-zero exits. When `tofu` behaves unexpectedly, the first question is always what was actually run. |
| FR-APP-30 | M | **Recoverability invariant.** No combination of settings may leave a capability unreachable by both mouse and keyboard. Enforced by a test that hides every panel and asserts each is still restorable by at least two independent paths. |
| FR-APP-31 | M | **At least one browsable surface always survives.** Hiding the menu bar reveals a primary menu button in the tab strip. Hiding the last remaining browsable surface is refused, with an explanation rather than a silent no-op. |
| FR-APP-32 | M | **Right-click on any chrome — tab strip, status bar, editor background — offers the panel toggles.** This is the mouse-only recovery path and it works regardless of what is hidden. |
| FR-APP-33 | M | **Hiding something states how to bring it back.** A transient message naming the shortcut, shown at the moment of hiding. The action has completed, so a toast is the correct container. |
| FR-APP-34 | M | **A "Reset layout" command** restoring defaults, reachable from the palette, the menu and every chrome context menu. |
| FR-APP-35 | M | **Peek.** Pressing a hidden panel's shortcut reveals it temporarily as an overlay without changing the saved layout; Escape dismisses, and a pin action makes it permanent. Looking at something should not require committing to it. |
| FR-APP-36 | M | **A keyboard reference overlay**, listing bindings in effect grouped by area, on a single memorable key. The command palette and this overlay are never hideable and never rebindable to nothing — they are the floor the invariant rests on. |
| FR-APP-37 | S | **Contextual panel suggestion.** When something occurs that a hidden panel exists to show — findings appear, tests fail, drift is detected — offer to reveal it, naming the shortcut. Strictly rate-limited: at most once per panel per session, dismissible permanently, never modal, never stealing focus. |
| FR-APP-38 | M | First run teaches exactly one thing: the command palette shortcut. Not a tour. Everything else is discoverable from there or from the menu. |
| FR-APP-09 | S | Open a PR directly from the application, with the plan summary, cost delta and exposure delta included in the PR body. |
| FR-APP-10 | C | Review and comment on PRs in-app, with the plan rendered rather than the raw diff. |

### 6.2 Editor and Language Intelligence

The acceptance bar for this whole area: **an author should be able to write a correct, compliant, non-obvious resource configuration without opening a browser tab to the provider registry and without knowing the attribute names in advance.**

| ID | Pri | Requirement |
|---|---|---|
| FR-ED-01 | M | Multi-file editor built on GtkSourceView 5, with a full HCL2 syntax definition. |
| FR-ED-02 | M | Structural understanding of the buffer via tree-sitter (`tree-sitter-hcl`), powering folding, structural navigation, block-level selection, and the refactoring operations in §6.5. Syntax highlighting from GtkSourceView; semantics from tree-sitter. |
| FR-ED-03 | M | LSP client speaking JSON-RPC over stdio to `terraform-ls`: go-to-definition, find-references, document and workspace symbols, rename-symbol, diagnostics, signature help. |
| FR-ED-04 | M | **Live speculative plan.** On save (debounced), run a read-only plan against real current state and render the diff in a side panel, with changed resources linked back to the lines that produced them. |
| FR-ED-05 | M | **Line-anchored verdicts, revealed progressively.** Policy, cost and exposure findings are attributed to the line of HCL that caused them. A gutter mark is always visible; the full explanation appears inline on the current line, on hover, or on demand — not permanently on every affected line. A finding the author cannot locate is a finding they will not fix, but a screen of permanent annotations is one they will stop reading. |
| FR-ED-18 | M | **Change map.** A vertical strip beside the scrollbar showing where this file's planned changes fall, marked by action, with replacements and exposure findings distinguished. Occupies the position a minimap would, and is more useful here than a thumbnail of the text. |
| FR-ED-19 | M | **Tab states are visually distinct**: active, inactive, hovered, unsaved, unreadable, and active-in-an-unfocused-split. Active versus inactive must be carried by background, text weight and an accent edge together — not by a single subtle shade, which fails at a glance, on a projector, and for anyone with reduced colour discrimination. |
| FR-ED-19a | M | **Four independent states, four dedicated slots.** A tab must be able to express all of these simultaneously without collision: focus (background, weight, top edge), version-control status (leading edge), unsaved buffer changes (trailing slot), and plan impact (bottom edge). No slot may be reused for a second meaning. |
| FR-ED-19b | M | **Version-control status on the tab**: untracked, modified, staged, conflicted, deleted from disk, unchanged. The same vocabulary and the same colours appear in the file rail, so the two surfaces never disagree. |
| FR-ED-19c | M | **Plan impact on the tab**: this file creates, changes, replaces or destroys resources in the current plan, or is untouched by it. Cleared whenever the plan is invalidated, so it can never show a stale verdict. |
| FR-ED-19d | M | **Colour is never the only carrier.** A setting selects bars, letters, or both, and the file rail always shows letters because it has the width for them. Hover states name every condition in words. |
| FR-ED-19e | M | **Indicator precedence is defined**, because a tab can be several things at once. Conflicted outranks modified outranks untracked. Destroy outranks replace outranks change outranks create. Unreadable outranks everything and suppresses plan impact entirely, since a file that cannot be parsed has no meaningful plan state. |
| FR-ED-20 | M | Tabs size to their content with a maximum width, disambiguate identical filenames with their containing path, and expose a close affordance on hover for every tab rather than only the active one. |
| FR-ED-21 | M | **Tab command set**: close, close others, close to the left, close to the right, close all, close saved, close tabs whose file is gone on disk, reopen last closed, pin, clone into a second view, split right, split down, move to another window, save, save as, save all, rename, duplicate, move, delete, reveal in rail, open containing folder, copy path variants, and compare with another open tab. |
| FR-ED-22 | M | **Scope variants live in a submenu, not at the top level.** Closing has four scopes and two filters; enumerating every combination as a flat list buries the one command people want. The common cases stay flat; the rest nest. |
| FR-ED-23 | M | **Any bulk close that would discard unsaved work states the count in the item itself** and offers review, discard and cancel. There is never a menu item whose only difference from its neighbour is whether it silently destroys work. |
| FR-ED-24 | M | **Plan-aware tab commands.** Close every tab the current plan does not touch, and sort tabs by the number of planned changes in each file. Both are only possible because the plan is already in memory, and both are more useful here than closing by modification state. |
| FR-ED-25 | S | Tab ordering: by name, by path, by most recently used, by plan impact, or manual. Manual is the default and drag reordering never fights an automatic sort. |
| FR-ED-26 | M | **Baseline editor capability.** Anything below this line makes the application feel unfinished to anyone arriving from a real editor, and none of it is optional: multiple cursors and multiple selections; expand selection to enclosing block; column selection; line operations (duplicate, delete, join, move up and down, swap); sort lines, reverse, unique, shuffle; toggle line and block comments; convert case; code folding by block and by level, plus fold-all and unfold-all; go to line; go to matching bracket; paste from history; render whitespace and invisibles; word wrap with a configurable column; rulers; configurable indentation with tab-to-space conversion; line-ending selection; encoding selection and reopen-with-encoding; find and replace with regex, in file and across the workspace; incremental search; bookmarks. |
| FR-ED-27 | S | **Code lens over blocks.** Above a resource block, show reference count, plan action, and cost where known — for example "3 references · replaced in plan · $248/mo". Toggleable, off for anyone who finds it noisy. |
| FR-ED-28 | S | **Inlay hints** rendering resolved values and expansion counts inline (FR-DBG-02, FR-DBG-03), as a display toggle independent of hover. |
| FR-ED-29 | M | Fold-all-resources and fold-to-level are first-class. A 900-line `main.tf` is normal, and folding is how it becomes navigable. |
| FR-ED-06 | M | **Diagnostics beyond the language server**: unused variables and locals, unreferenced outputs, `count`/`for_each` misuse, references to attributes absent from the pinned provider version, deprecated attributes, and violations of configured conventions such as required tags. |
| FR-ED-07 | M | **Round-trip safety.** Never reformat, reorder or rewrite files except `terraform fmt` on explicit action. No proprietary markers, sidecar files or generation fences. Files must be equally editable in vim, VS Code or Backsight. |
| FR-ED-08 | M | Never render values marked sensitive. Detect hardcoded credentials while editing, before commit. |
| FR-ED-09 | M | Project tree, fuzzy file navigation, and search-and-replace across the workspace. |
| FR-ED-10 | M | Integrated operations without a terminal: `init`, `validate`, `fmt`, `plan`, `state list`, `state show`. |
| FR-ED-11 | S | Diff against base branch within the editor. |
| FR-ED-12 | S | Configurable keymaps, including vim bindings for those who want them. Default bindings are conventional GNOME/GTK, not modal. |
| FR-ED-13 | S | Background convergence run against MiniStack, non-blocking, results streamed in. |
| FR-ED-14 | C | Editor extension for VS Code exposing the same schema service, live plan and exposure feedback, for engineers who will not change editors. |

### 6.3 Provider Schema, Documentation and Completion

Completion quality in Terraform is a direct function of provider schema availability. Everything below is served from local disk.

| ID | Pri | Requirement |
|---|---|---|
| FR-SCH-01 | M | **Local schema index.** Ingest `terraform providers schema -json` once per provider *version*, index it into local storage, and serve all completion, hover and snippet generation from that index. Never block the editor on an in-session `terraform init`. |
| FR-SCH-02 | M | **Version-pinned resolution.** Serve the schema matching the provider version in the workspace's dependency lock file, never the newest available. Completing `aws` 6.x attributes into a workspace pinned at 5.x is worse than no completion. |
| FR-SCH-03 | M | **Mirror provider documentation locally.** Provider prose documentation lives in each provider's own source repository and is rendered from there by the registry, so it can be vendored per version alongside the schema. |
| FR-SCH-04 | M | **Fully offline once mirrored.** No network access required for any authoring capability. Ship a bundled index for common providers (aws, null, random, tls, external, http); mirror others on first use or on demand. |
| FR-SCH-05 | M | Hover shows: type, required or optional, default, **whether the attribute forces replacement**, deprecation status, description, and a link into the documentation panel. |
| FR-SCH-06 | M | **Force-replacement is surfaced at authoring time.** The schema declares which attributes are `ForceNew`. The author sees it as they type, not in a plan twenty minutes later. This is the highest-value information the schema carries and no general-purpose editor surfaces it. |
| FR-SCH-07 | M | Documentation panel: browse and search all mirrored provider docs, version-matched, with examples insertable into the buffer. |
| FR-SCH-08 | M | Full-text search across providers by resource name, data source name, attribute name and description, so an author who knows what they want but not what it's called can find it. |
| FR-SCH-09 | M | **Schema-driven completion**: resource types, data sources, arguments, nested blocks, and enumerated values wherever the schema constrains them. Required arguments visually distinguished from optional. |
| FR-SCH-10 | M | **Reference completion**: variables, locals, outputs, resource and data source attributes, module outputs, and remote state outputs, resolved from the dependency graph rather than by text matching. |
| FR-SCH-11 | M | **Value completion from the live account.** Using the user's own read-only credentials, complete real values: instance types available in region, AMI IDs, availability zones, VPC/subnet/security group IDs, KMS aliases, IAM role ARNs, certificate ARNs, hosted zone IDs. Cached on disk with per-type TTLs. Degrades cleanly to schema-only when offline or unauthorised. |
| FR-SCH-12 | M | **Policy-aware completion.** Values forbidden by the configured policy set are excluded or demoted and marked with the rule that forbids them. Compliant values rank first, so compliant code is easier to write than non-compliant code. |
| FR-SCH-13 | S | **Cost-annotated completion.** Estimated monthly cost shown inline against price-bearing enumerated values at the moment of choosing. |
| FR-SCH-14 | M | **Catalog-first completion.** Where an approved internal module exists for the resource being written, offer the module above the raw resource type. |
| FR-SCH-15 | M | **Generated snippets.** Every resource and data source type gets snippets generated from its schema — a required-arguments-only variant and a full commented variant. Generated, never hand-maintained, so coverage is complete and current by construction. |
| FR-SCH-16 | M | **Module snippets** generated from catalog module variable schemas, with required variables as ordered tab stops. |
| FR-SCH-17 | M | **Organisation snippets** authored by platform teams, distributed via a git repository, version-controlled. |
| FR-SCH-18 | M | Snippet tab stops carry defaults from schema defaults and configured conventions — naming patterns, required tags, standard lifecycle blocks — so the first draft is already close to compliant. |
| FR-SCH-19 | M | Snippets for the meta-constructs authors routinely get wrong: `moved`, `import`, `lifecycle`, `dynamic`, `for_each` over a map, conditional `count`, provider aliasing, backend configuration. |
| FR-SCH-20 | M | Completion must never suggest, complete or cache secret values, and never offer inline credential patterns. |
| FR-SCH-21 | M | Administrative view of mirrored provider versions, disk used, staleness, and one-action update. Deduplicate by provider and version across workspaces. |
| FR-SCH-22 | S | Index Terraform language documentation — functions, meta-arguments, expressions — with signature help. |

### 6.4 Guided Authoring and Module Catalog

| ID | Pri | Requirement |
|---|---|---|
| FR-CAT-01 | M | Module catalog sourced from configured git repositories or a private registry, with versions, documentation, examples, owner and deprecation status, indexed locally and browsable offline. |
| FR-CAT-02 | M | Scaffold a resource or workspace from a catalog module via a form generated automatically from the module's variable schema — types, defaults, descriptions and `validation` blocks drive the form. No hand-maintained form definitions. |
| FR-CAT-03 | M | Generated output is plain idiomatic HCL the user owns and edits freely. No hidden generation layer, no regeneration lock-in. |
| FR-CAT-04 | M | Golden path templates per workload archetype (stateless service, datastore, queue, static site, scheduled job), composed of catalog modules and pre-validated against the policy set so a scaffolded workspace passes by construction. |
| FR-CAT-05 | S | Flag workspaces using deprecated or outdated module versions and offer an upgrade. |
| FR-CAT-06 | M | Catalog modules appear in the documentation panel with pages generated from their variable and output schemas plus README, so internal modules are as discoverable as upstream resources. |

### 6.5 Refactoring

The highest-consequence code path in the product. A bug here destroys production resources.

| ID | Pri | Requirement |
|---|---|---|
| FR-REF-01 | M | **Rename with state safety.** Renaming a resource updates every reference and generates the corresponding `moved` block. |
| FR-REF-02 | M | **Extract to module**, generating the required `moved` blocks for every relocated resource. |
| FR-REF-03 | M | **Every refactor is verified before being offered as complete**, by running a plan and confirming zero destructive actions. If it cannot be made non-destructive, Backsight says so explicitly and refuses rather than proceeding. |
| FR-REF-04 | M | **`count` to `for_each` conversion** with generated `moved` blocks mapping index to key. Among the most common causes of accidental destruction in Terraform; must be first-class and verified. |
| FR-REF-05 | S | **Import block generation** for existing unmanaged resources discovered in the account, with configuration scaffolded from the live resource's attributes. |
| FR-REF-06 | S | **Provider upgrade assistance** — diff schemas between versions and flag every removed, renamed or newly deprecated attribute in the workspace, with suggested edits. |
| FR-REF-07 | M | All refactors are atomic and undoable as a single operation in the editor. |

### 6.6 Exposure and Reachability Analysis

Existing scanners evaluate resources in isolation. This evaluates paths across the projected graph, including resources already in state that are not part of the change.

| ID | Pri | Requirement |
|---|---|---|
| FR-EXP-01 | M | Construct a **projected resource graph** = current state + plan delta, extended across workspaces wherever remote state data sources exist. |
| FR-EXP-02 | M | **Network reachability.** Determine whether a resource becomes reachable from the public internet, resolving security group rules through attached ENIs, instances, load balancers and endpoints, to subnets, route tables, internet and NAT gateways, and network ACLs. |
| FR-EXP-03 | M | **Data exposure.** Public S3 buckets and objects, public RDS instances, public snapshots and AMIs, public ECR repositories, missing encryption at rest, missing encryption in transit. |
| FR-EXP-04 | S | **IAM privilege-escalation paths** — `iam:PassRole` combined with service assumption, policy attachment rights, trust policy widening, wildcard resource grants. |
| FR-EXP-05 | M | Report findings as a **delta**: what this change *newly* exposes, held separate from pre-existing exposure. Reviewers flooded with legacy findings ignore all findings. |
| FR-EXP-06 | M | Every finding carries the reachability path as evidence, hop by hop, verifiable without trusting the tool. |
| FR-EXP-07 | M | False positives are a first-class concern: baseline suppression, per-finding acknowledgement with expiry, and an internally tracked false-positive rate that gates release. |
| FR-EXP-08 | M | Where the graph is incomplete — cross-account references, unmanaged resources, unsupported types — say so explicitly and mark the analysis partial. **A silent false negative is worse than a false positive.** |
| FR-EXP-09 | M | Surface findings live in the editor, anchored to the causing line (FR-ED-05). |
| FR-EXP-10 | M | Analysis runs locally. No plan, state or account data leaves the machine. |

### 6.7 Convergence Testing (MiniStack)

| ID | Pri | Requirement |
|---|---|---|
| FR-SIM-01 | M | Manage a local MiniStack container via Docker or Podman: pull, start, health check, reset between runs using its state-reset endpoint, stop. The user never types a container command. |
| FR-SIM-02 | M | **Inject provider endpoint redirection without modifying user code** — generate an override redirecting the AWS provider to the local endpoint and disabling credential validation, metadata lookup and account-ID resolution. |
| FR-SIM-03 | M | Execute a full apply against the sandbox; report success, failure or partial failure with the specific resource address and provider error. |
| FR-SIM-04 | M | Maintain a service coverage matrix for the installed MiniStack version and display **Simulation Coverage** as a percentage per run. |
| FR-SIM-05 | M | Below a configurable coverage threshold (default 80%), present the result as *partial* and name every uncovered resource. A partial pass must never carry the visual weight of a full pass. |
| FR-SIM-06 | M | Never present a sandbox result as a prediction of production behaviour. All copy frames this as a **correctness gate** — "this configuration applies cleanly" — never a preview. |
| FR-SIM-07 | S | Seed the sandbox with a synthesised approximation of current state, rewriting account IDs, ARNs and region identifiers, so update and destroy paths are exercised, not only creates. |
| FR-SIM-08 | S | Data-source stubbing for data sources referencing real resources absent from the sandbox, with unstubbed sources reported as coverage gaps rather than hard failures. |
| FR-SIM-09 | S | Post-convergence assertions — user-authored checks executed against the converged sandbox. |
| FR-SIM-10 | M | Detect absence of Docker or Podman and degrade gracefully with clear guidance, rather than failing obscurely. |

### 6.8 Policy and Cost

| ID | Pri | Requirement |
|---|---|---|
| FR-POL-01 | M | Evaluate OPA/Rego policies locally against the plan, sourced from a configured git repository so a platform team can distribute one policy set to every workstation. |
| FR-POL-02 | M | Bundle Checkov and Trivy, results merged into a single findings view alongside Rego results. |
| FR-POL-03 | M | Policy severity levels drive presentation, not enforcement. **v1 governance is advisory** — the desktop application cannot prevent a determined user from running `terraform apply` directly. Enforcement is §12. |
| FR-POL-04 | S | Local suppression with justification and expiry, recorded in the workspace so it travels with the code and is reviewable in the PR. |
| FR-POL-05 | M | Monthly cost delta per plan: current, projected, difference, per resource. |
| FR-POL-06 | M | Self-contained pricing data, refreshed on demand, functional offline. Usage-dependent resources marked as not estimable rather than reported as zero. |

### 6.9 Credentials and Security

| ID | Pri | Requirement |
|---|---|---|
| FR-SEC-01 | M | **AWS IAM Identity Center (SSO) as the primary credential path.** The user authenticates as themselves; Backsight assumes roles with their permissions and holds only short-lived session credentials. |
| FR-SEC-02 | M | **No long-lived cloud credentials stored by the application, ever.** Existing shared-config profiles and environment credentials are honoured if present, but never copied, cached or persisted by Backsight. |
| FR-SEC-03 | M | Session credentials held in memory for their lifetime; any on-disk cache uses the system keyring via Secret Service. |
| FR-SEC-04 | M | Distinct role selection per operation where the user's SSO configuration provides it: read-only for planning, exposure analysis and value completion; write only for apply. |
| FR-SEC-05 | M | Explicit, unmistakable confirmation before any apply, showing the target account, region, role and the destroy/replace counts. |
| FR-SEC-06 | M | Never transmit code, state, plans or account data off the machine. Network egress limited to the provider registry, module sources, the AWS API, the configured VCS, and the policy/catalog repositories. |
| FR-SEC-07 | M | Application state, caches and working data stored under XDG directories with restrictive permissions. |
| FR-SEC-08 | S | Local activity log — every plan, apply, refactor and policy decision, timestamped and exportable. Useful for personal recall and for reconstructing what happened; **explicitly not tamper-evident audit evidence**, which requires §12. |

### 6.10 State and Apply

| ID | Pri | Requirement |
|---|---|---|
| FR-ST-01 | M | Support remote state backends (S3 with DynamoDB or native locking) and local state. Backsight is not a state backend. |
| FR-ST-02 | M | Respect and surface backend state locking; show clearly when a workspace is locked and by whom. |
| FR-ST-03 | M | Apply only a plan artifact produced and reviewed in-app; never re-plan silently between review and apply. |
| FR-ST-04 | M | Stream apply output live, and persist the full output locally with the plan that produced it. |
| FR-ST-05 | M | On interrupted apply, detect the indeterminate state on next launch and guide the user through reconciliation rather than silently re-planning. |
| FR-ST-06 | M | State inspection and version browsing where the backend supports it. |
| FR-ST-07 | M | Documentation must state plainly that Terraform apply has no general rollback; the recovery path is a corrective change. |
| FR-ST-08 | S | On-demand drift check for a workspace (refresh-only plan). Scheduled drift detection requires §12. |

### 6.11 Stacks and Dependencies

A workspace is a directory. A **stack** is a deployable unit with an identity — code location, engine, backend, environment, variables, credential binding, and its relationships to other stacks. The distinction matters because dependencies exist between deployable units, not between folders.

| ID | Pri | Requirement |
|---|---|---|
| FR-STK-01 | M | **Declarative stack definitions in version control** — name, path, engine and version, backend, environment, variables, and the account and role binding. No stack may exist only in local application state; the graph must be shareable by committing a file. |
| FR-STK-02 | M | **Explicit dependency edges.** Declared, never inferred. An inferred graph that is quietly wrong is more dangerous than no graph at all. |
| FR-STK-03 | M | **Cross-stack data flow** via declared outputs consumed as inputs, resolved through remote state data sources. Consuming an output the producer does not expose is a validation error at parse time, not a plan failure twenty minutes later. |
| FR-STK-04 | M | Cycle detection, naming the specific cycle. |
| FR-STK-05 | M | Stack graph view: every stack, its edges, status, last apply, drift state and lock state. |
| FR-STK-06 | M | **Blast radius.** While editing a stack, show which downstream stacks consume its outputs, and specifically which of those outputs this change touches. This is the authoring-loop half of dependency management, and it is the half that belongs on the desktop. |
| FR-STK-07 | S | **Impact plan.** Speculative plan of directly affected downstream stacks after an upstream change. Opt-in per run — it is expensive and needs credentials for every downstream stack. |
| FR-STK-08 | M | Compute and display the correct topological order for a multi-stack change. Applies are performed one stack at a time under explicit user control. **No automated multi-stack apply in v1** (§12). |
| FR-STK-09 | M | Stack definitions parse, validate and graph entirely offline. |
| FR-STK-10 | S | Environment promotion — the same stack definition bound to a different environment, with a diff of the two variable sets. |
| FR-STK-11 | S | Policy and lane binding at stack level, so governance attaches to the deployable unit rather than the directory. |
| FR-STK-12 | C | Stack scaffolding from the catalog — a golden path that produces a whole stack, not just a resource. |

---

### 6.12 Testing

Terraform ships a native test framework — `.tftest.hcl` files with `run` blocks, assertions and provider mocking. It is under-used largely because running and reading the results is unpleasant. Backsight has a sandbox already; combining the two produces something no other tool offers.

| ID | Pri | Requirement |
|---|---|---|
| FR-TST-01 | M | Discover `*.tftest.hcl` across the workspace and present a test tree grouped by file and `run` block. |
| FR-TST-02 | M | Run everything, a file, or a single `run` block — from the tree, the gutter, the palette or a key. |
| FR-TST-03 | M | **A failing assertion shows its condition, the evaluated value of every expression it references, and the error message.** "Assertion failed" alone is the reason people abandon the test framework. |
| FR-TST-04 | M | Gutter marks on `run` and `assert` blocks carrying the last result, clickable to re-run just that block. |
| FR-TST-05 | M | **Select the execution target per run: provider mocks, MiniStack, or real infrastructure.** Mocks are fast and shallow; MiniStack performs a real apply with no cost and no risk; real infrastructure is available and never the default. |
| FR-TST-06 | M | **Tests that would touch real infrastructure require the same confirmation as any apply.** `command = apply` without mocks creates and destroys real resources. Without this, one keystroke bills the user for a database. |
| FR-TST-07 | M | Surface `check` blocks and `precondition`/`postcondition` in the same view as tests. They are assertions with a different execution moment, and splitting them across two surfaces hides half the safety net. |
| FR-TST-08 | S | Scaffold a test file from a module's variables and outputs, with a `run` block per documented example. |
| FR-TST-09 | S | Report which outputs and resources are asserted on by at least one test and which are not. |
| FR-TST-10 | S | Run tests on save, opt-in and debounced, with results in the gutter. |
| FR-TST-11 | S | Backsight's own policy tests (FR-POL-06) appear in the same runner, so one view answers "is this workspace healthy". |

### 6.13 Debugging HCL

HCL cannot be stepped through, so debugging today means adding an output and re-planning. Everything below is derivable from data Backsight already holds — the plan JSON, the schema index and the state.

| ID | Pri | Requirement |
|---|---|---|
| FR-DBG-01 | M | **Expression evaluation.** Select an expression and evaluate it in the workspace's real context — variables, locals, data sources, state. A console for free-form evaluation, with completion from the schema index. |
| FR-DBG-02 | M | **Inline resolved values.** Hovering a variable, local or reference shows what it actually resolved to in the current plan, not its declaration. |
| FR-DBG-03 | M | **`for_each` and `count` expansion preview.** Show the expanded key set or instance count at the point of declaration. Expansion surprises are the single largest source of confusion in HCL, and the answer is computable before planning. |
| FR-DBG-04 | M | **Distinguish known from unknown.** Mark which parts of an expression are unknown at plan time. A large class of "why is my plan showing this" is answered by seeing that a value is not yet known. |
| FR-DBG-05 | M | **Replacement trace.** From a replaced resource, to the attribute forcing replacement, to the expression producing that attribute, to the variable or upstream resource whose change caused it. The plan states *that* a resource is replaced; this answers *why*. |
| FR-DBG-06 | M | **Sensitive values are never revealed** by evaluation, hover or console. They render as sensitive, and no setting turns that off. |
| FR-DBG-07 | S | Structured provider interaction log for a plan, apply or convergence run — operation, resource, duration, error — instead of raw `TF_LOG` output. Especially valuable against MiniStack, where failures are otherwise opaque. |
| FR-DBG-08 | S | Dependency view for a single resource: what it depends on, what depends on it, and the path between any two. |

---

## 7. Non-Functional Requirements

### 7.1 Performance and Footprint

These are the "lean" requirements, and they are testable acceptance criteria rather than aspirations.

| ID | Requirement |
|---|---|
| NFR-01 | Cold start to interactive window ≤ 2 seconds on reference hardware. |
| NFR-02 | Idle resident memory ≤ 250 MB, excluding containers Backsight manages. |
| NFR-03 | Installed size ≤ 200 MB excluding the provider schema and documentation mirror. |
| NFR-04 | Keystroke-to-diagnostic latency ≤ 300 ms (p95); the UI thread must never block on any operation. |
| NFR-05 | Completion list returned ≤ 150 ms (p95) for schema-driven completion, ≤ 500 ms (p95) for cached account value completion. |
| NFR-06 | Hover documentation rendered ≤ 200 ms (p95), served from local disk with no network call. |
| NFR-07 | Live speculative plan visible ≤ 15 seconds (p50) for a workspace of ≤ 200 resources with a warm provider cache. |
| NFR-08 | Exposure analysis complete ≤ 10 seconds (p50) after plan availability. |
| NFR-09 | Open and highlight a 5,000-line HCL file ≤ 300 ms. |
| NFR-10 | Schema index for the AWS provider builds ≤ 60 seconds on first use and is reused thereafter. |

### 7.2 Other

| ID | Category | Requirement |
|---|---|---|
| NFR-11 | Offline | 100% of authoring capability functions without connectivity once schemas are mirrored. Degradation is limited to live plan, value completion and apply. |
| NFR-12 | Accuracy | Exposure analyser false-positive rate ≤ 5%, false-negative rate ≤ 1% against a curated benchmark corpus, measured and gating each release. |
| NFR-13 | Privacy | No telemetry, no phone-home, no analytics. Any future diagnostics are opt-in and locally inspectable. |
| NFR-14 | Compatibility | Support current and two prior minor versions of Terraform and OpenTofu. |
| NFR-15 | Accessibility | GNOME accessibility conventions; full keyboard operability; destroy and replace never distinguished by colour alone. |
| NFR-16 | Portability | All user data — code, config, snippets, suppressions, activity log — in open formats on disk, with no proprietary encoding and no lock-in. |
| NFR-17 | Upgrade | Configuration and local indexes survive upgrades; schema mirror rebuild is never required by a version bump. |

---

## 8. Key Design Decisions

| ID | Decision | Rationale |
|---|---|---|
| DD-1 | Desktop application, not a web application. | The product's value is in the authoring loop, which needs local state, local containers, local credentials and sub-second latency. A browser adds a network hop to every one of those. |
| DD-2 | v1 governance is advisory; enforcement deferred to §12. | A local process cannot enforce anything against a user who can run `terraform` directly. Pretending otherwise would be dishonest to buyers and would fail the first audit. |
| DD-3 | AWS IAM Identity Center rather than Backsight-as-OIDC-provider. | A laptop cannot be an OIDC issuer AWS trusts, and making every workstation a credential-minting authority would be a serious security regression. |
| DD-4 | MiniStack rather than LocalStack. | MIT-licensed, no paid tier gating core services, no licence key, no telemetry, small image, fast start — all prerequisites for bundling into a desktop tool and for offline use. |
| DD-5 | Convergence testing is a correctness gate, not a preview. | Emulator coverage gaps are inevitable; framing it as prediction guarantees a user will eventually be badly burned. |
| DD-6 | Provider schemas and documentation are a **local, version-indexed store**, not a per-session `terraform init` side effect. | Per-session init cannot meet interactive latency targets and fails entirely offline. |
| DD-7 | Value completion is best-effort and degrades to schema-only. | It requires account access some users won't have and connectivity they won't always have. The editor must be fully usable without it. |
| DD-8 | Snippets are generated from schemas, not hand-authored. | Hand-maintained snippet libraries cover a fraction of resource types and rot against provider releases. Generation gives complete, current coverage for free. |
| DD-9 | Round-trip safety is a hard constraint. | Any file mangling makes Backsight unusable alongside the editors people already have, and adoption dies. |
| DD-10 | The refactor engine refuses rather than guesses. | The failure mode is destroyed production infrastructure. A refused refactor costs a minute; a wrong one costs a database. |
| DD-11 | Exposure analysis operates on the projected graph including existing state, not on the diff. | The diff-only view is precisely why current scanners miss real exposure. |
| DD-12 | Everything is built to attach to §12 without rework. | Plan artifacts, findings, activity records and policy decisions use stable serialisable formats from day one, so the v2 service consumes them rather than requiring a rewrite. |
| DD-13 | The stack graph lives in version control, not in the application. | This is what makes stacks possible at all on a desktop-first product — the graph is shared by committing a file, not by running a server. The v2 Hub inherits it unchanged. |
| DD-14 | Dependencies are declared, never inferred. | Inference from remote state data sources looks clever and is silently wrong often enough to be dangerous. A wrong graph produces a confident, incorrect blast radius. |
| DD-15 | v1 computes apply order; humans execute it one stack at a time. | Orchestrated multi-stack apply needs an authority that survives the laptop closing. A machine that dies mid-sequence leaves a half-deployed estate and nothing with standing to resume it. |
| DD-16 | The interaction model is editor-first: chrome recedes, panels are transient, the palette carries the surface area. | Persistent rails for plan, cost, policy, exposure and convergence would consume half the window to display, most of the time, nothing. The differentiators are worth showing at the moment they have something to say and worth hiding otherwise. This also reduces always-on decoration density, which is the largest risk in OQ-6. |
| DD-17 | The palette must be discoverable, not merely powerful. | A palette-first tool is superb for daily users and unusable for the Occasional Author persona. Suggested commands on open, and visible chrome for the few irreversible actions, are what keep both personas served. |
| DD-18 | Mouse parity is the discovery surface, not an accessibility afterthought. | You cannot search a palette for a command whose name you do not know. Menus and context menus are browsable, so they are how an occasional user finds a capability for the first time. This is why FR-APP-15 is a Must and not a Should. |
| DD-19 | Layout is the user's, and it persists per workspace. | Every strong opinion about panel layout is wrong for somebody. Shipping a good default and then getting out of the way costs little and removes an entire category of complaint. |
| DD-20 | Tests run against mocks by default, MiniStack on request, real infrastructure only behind an apply confirmation. | The sandbox turns `tofu test` from a mocking exercise into a real apply-and-assert loop at no cost and no risk — a capability that exists only because convergence testing was already built. Defaulting to real infrastructure would make the test runner a billing hazard. |
| DD-21 | A menu bar, against libadwaita convention. | The primary-menu pattern is designed for applications with a dozen commands. This one has hundreds, and the menu bar is the browsable surface that makes mouse parity (DD-18) real. It is hideable for anyone who disagrees, with a primary menu fallback so nothing becomes unreachable. |
| DD-22 | The baseline editor capabilities are requirements, not assumptions. | Multiple cursors, folding, line operations and comment toggling are invisible when present and disqualifying when absent. A specification that lists only the novel capabilities produces a tool nobody can use for an hour. |
| DD-23 | Configurability creates a recoverability obligation. | The moment panels can be hidden, a user can hide the thing that would have told them how to unhide it. Shortcuts alone do not solve this, because the knowledge of which shortcut is precisely what was lost. Two independent recovery paths per panel, always, and a floor of surfaces that cannot be hidden at all. |

---

## 9. Technical Constraints

### 9.1 Mandated

- **Language:** Python 3.12+ for the application and UI.
- **UI toolkit:** GTK4 with libadwaita, via PyGObject.
- **Editor widget:** GtkSourceView 5.
- **Prohibited:** Java or any JVM component. No embedded browser engine — no WebKit, no Chromium, no Electron. This rules out Monaco and CodeMirror, which would each cost 150 MB+ of resident memory before a file is opened, in direct conflict with NFR-02.

### 9.2 Editor Architecture

GtkSourceView provides the buffer, rendering and syntax highlighting via an HCL2 language definition. Structural and semantic understanding comes from `tree-sitter-hcl` via `py-tree-sitter`, which powers folding, block navigation and — critically — the refactoring operations, since text-based rewriting of HCL is not safe enough for FR-REF-03.

A minimal LSP client must be built: there is no mature PyGObject LSP client, so a JSON-RPC-over-stdio client for `terraform-ls` is a first-party component. It should be small and cover only the methods used.

### 9.3 Background Language Choice

Start in pure Python. Escalate specific hot paths to a compiled extension (Rust via PyO3) **only when profiling demonstrates a need** — the likely candidates being the exposure graph traversal and the schema index build. Introducing a second language pre-emptively costs build complexity, packaging complexity and contributor accessibility, and buys nothing until there is a measured problem.

### 9.4 Storage and Concurrency

- **Storage:** SQLite for the schema index, documentation mirror, completion cache and activity log, with FTS5 for full-text search (FR-SCH-08). No server, no daemon, one file, trivially portable.
- **Concurrency:** all subprocess work (`terraform`, `terraform-ls`, container operations) runs off the GTK main loop via async integration. NFR-04 requires that the UI thread never blocks; this is an architectural constraint, not a tuning exercise.

### 9.5 Packaging

`.deb` first, targeting Ubuntu LTS. Flatpak, Snap and AppImage follow.

**Confinement is a real constraint, not a formality.** MiniStack requires access to a container runtime, and both Snap's confinement and Flatpak's sandbox restrict access to the Docker or Podman socket. Podman in rootless mode is the better fit for confined packaging and should be the preferred runtime. Each packaging format must be validated end-to-end with convergence testing working, not merely "the app launches" — otherwise the confined builds ship with the differentiating feature broken.

---

## 10. Risks

| ID | Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| R-1 | **Terraform's BUSL licence.** HashiCorp's licence restricts use in products competitive with theirs. A commercial Terraform IDE is closer to that line than a CI wrapper. | Critical | Medium | **Legal review before any engineering commitment.** Lead with OpenTofu as the default engine; never distribute the Terraform binary; seek written clarification. Weight depends on OQ-1. |
| R-2 | Refactor operations that manipulate `moved` and `import` blocks destroy production resources through a bug. | Critical | Medium | FR-REF-03 verification gate, tree-sitter-based rewriting rather than text manipulation (§9.2), sandbox validation, and a release-blocking regression corpus of refactor cases. |
| R-3 | Exposure analyser **false negatives** — incomplete graph produces silent misses, which are worse than noise. | Critical | Medium | FR-EXP-08 explicit partial marking. Never present partial analysis as clean. NFR-12 measured and release-gating. |
| R-4 | Exposure analyser false positives train users to dismiss all findings. | High | High | FR-EXP-05 delta-only reporting, FR-EXP-06 verifiable evidence paths, FR-EXP-07 suppression with expiry, NFR-12. |
| R-5 | Users read a green convergence result as a production guarantee. | High | High | FR-SIM-04/05/06. Coverage always visible; copy audited for prediction language; onboarding teaches the distinction. |
| R-6 | MiniStack coverage insufficient for real configurations, leaving the feature perpetually partial. | High | Medium | Measure coverage against a corpus of real configurations before committing to the feature's prominence. Contribute upstream for high-frequency gaps. |
| R-7 | MiniStack is a single-point external dependency for a headline feature. | High | Low | MIT licence permits vendoring and forking. Abstract the emulator behind an interface so an alternative can be substituted. |
| R-8 | **Adoption.** Engineers have editors they love and will not switch. | Critical | High | The differentiators must be things VS Code cannot do — value completion, force-replacement hover, live plan, exposure analysis, verified refactoring. If it is only a nicer text editor, it fails. Validate with real users before P2. FR-ED-14 extension as the hedge. |
| R-9 | Value completion requires read describe access and adds API latency and rate-limit pressure. | Medium | Medium | DD-7 graceful degradation, disk caching with long TTLs for slow-changing values, per-account request budgeting, per-workspace opt-out. |
| R-10 | Provider version proliferation makes the local schema and documentation mirror large and slow to update. | Medium | Medium | FR-SCH-21 — deduplicate by provider and version, garbage-collect unreferenced versions, lazy mirroring on first use, visible disk accounting. |
| R-11 | Python performance fails NFR-04/05/09 on large workspaces. | High | Medium | §9.3 — profile early against a deliberately large corpus; escalate specific paths to compiled extensions. Establish the performance corpus in P1, not P4. |
| R-12 | Snap and Flatpak confinement breaks container access, shipping the convergence feature broken. | High | High | §9.5 — Podman rootless preferred; every packaging format validated end-to-end with convergence working before release. |
| R-13 | GTK4/libadwaita restricts the product to Linux, limiting the addressable market. | Medium | High | Accepted deliberately: Ubuntu-first is the stated requirement. Keep UI code separable from the engine so a future port is a UI rewrite, not a product rewrite. |
| R-14 | v1 has no enforcement, so security and compliance buyers see no value until v2. | High | High | Position v1 honestly as a developer tool, not a control plane. DD-12 ensures v2 attaches without rework. Do not sell v1 as governance. |
| R-15 | Scope: editor, schema service, catalog, refactoring, exposure analyser, convergence, policy, cost — in one v1. | Critical | High | §11 phasing with hard go/no-go gates. The exposure analyser and the editor are the two genuinely novel builds and are deliberately separated across phases. |

---

## 11. Phasing

| Phase | Contents | Go/no-go gate |
|---|---|---|
| **P1 — Workbench** | Application shell, workspace management, GtkSourceView editor, tree-sitter integration, terraform-ls client, local schema index and documentation mirror, schema-driven completion and generated snippets, live speculative plan, SSO credentials, plan and apply. | NFR-01 to NFR-09 met on the performance corpus. A Terraform author prefers it to VS Code for a real task. |
| **P2 — Safety** | Verified refactoring, MiniStack convergence testing, policy and cost integration, line-anchored verdicts. | Refactor regression corpus passes 100%. Convergence coverage measured against real configurations. |
| **P2b — Stacks** | Declarative stack definitions, dependency graph, cycle detection, cross-stack output validation, graph view, blast radius. | Blast radius correct on a real multi-stack estate, verified against a human-drawn dependency map. |
| **P3 — Intelligence** | Exposure and reachability analysis, value completion from the account, policy-aware and cost-annotated completion. | NFR-12 accuracy targets met on the benchmark corpus. |
| **P4 — Golden path** | Module catalog, schema-driven scaffolding, golden path templates, organisation snippet distribution. | Scaffolding measurably faster than copy-paste for a real workload. |
| **P5 — Distribution** | Flatpak, Snap and AppImage packaging; PR creation and review; on-demand drift. | Convergence testing verified working in every packaging format. |
| **v2 — Hub** | §12. | Separate business case. |

---

## 12. Deferred to v2: The Hub

These capabilities were specified in v0.2/v0.3 and cannot be delivered by a desktop application. They are recorded here so the boundary is explicit and so v1 is built to attach to them.

| Capability | Why it cannot live on a laptop |
|---|---|
| **Approvals** | An approval recorded on the approver's machine is not evidence. Requires a trusted third party. |
| **Tamper-evident audit** | A local log the user can edit is not an audit trail. FR-SEC-08 is personal recall, not compliance evidence. |
| **Policy enforcement** | A local process cannot stop someone running `terraform apply` directly. Enforcement requires control of the credential path or the merge. |
| **OIDC credential issuance** | Requires a stable, publicly discoverable issuer that AWS trusts. Per-workstation issuers would be a security regression. |
| **Scheduled drift detection** | Does not run when the lid is closed. |
| **Organisation-wide DORA and reliability metrics** | Needs a store that is not one person's disk, and a join across everyone's activity. |
| **Delivery lanes and boundary escalation** | Governance routing is only meaningful where it can be enforced. |
| **Separation of duties** | Requires an authority that is not the person performing the action. |
| **Orchestrated multi-stack apply** | Ordered execution across stacks needs an authority that survives a closed laptop, plus cross-stack locking and resumption after failure mid-sequence. v1 computes the order and shows it; a human runs it. |

**Design obligations on v1 to make this attachment cheap:** stable serialisable formats for plan artifacts, findings, policy decisions and activity records; a clean boundary between the analysis engine and the UI; credential handling abstracted so an OIDC path can be added without touching the editor; and no assumption anywhere in the codebase that the user and the actor are the same entity.

---

## 13. Success Metrics

| Metric | Target |
|---|---|
| Cold start | ≤ 2 seconds |
| Idle memory | ≤ 250 MB |
| Median save-to-live-plan | ≤ 15 seconds |
| Completion latency (p95) | ≤ 150 ms |
| Weekly retention among engineers who write Terraform weekly | ≥ 60% at 8 weeks |
| Users reporting Backsight as their primary Terraform editor at 8 weeks | ≥ 40% |
| Accidental destructive refactors performed by users | 0 |
| Exposure analyser false-positive rate | ≤ 5% |
| Convergence coverage on a representative configuration corpus | ≥ 80% |
| Resources scaffolded from catalog vs written from scratch | ≥ 50% |
| Stored long-lived cloud credentials on user workstations | 0 |

---

## 14. Assumptions

- **A-1** Users have Docker or Podman available, or can install it. Convergence testing is unavailable without it.
- **A-2** Target organisations use AWS IAM Identity Center or can adopt it. Without SSO, FR-SEC-01 degrades to honouring existing profiles.
- **A-3** Read describe access is available for value completion. *Unvalidated — OQ-4.*
- **A-4** A meaningful population of Terraform is written by engineers who are not experts, making guided authoring valuable. *Unvalidated — OQ-5.*
- **A-5** MiniStack remains actively maintained and MIT-licensed. *Single-point dependency; R-7.*
- **A-6** GtkSourceView 5 is sufficient as an editor foundation without a custom widget. *Requires a spike in P1 — OQ-6.*
- **A-7** Engineers will accept a dedicated application rather than an extension in their existing editor. *The central adoption bet; R-8.*

---

## 15. Dependencies

| Dependency | Purpose | Risk if unavailable |
|---|---|---|
| GTK4, libadwaita, PyGObject | Application and UI | Product non-viable as specified |
| GtkSourceView 5 | Editor buffer and highlighting | Custom editor widget required; large cost |
| tree-sitter-hcl, py-tree-sitter | Structural parsing, refactoring | Refactoring becomes unsafe text manipulation |
| terraform-ls | Language intelligence | Completion degraded to schema-only |
| Provider schemas | Completion, snippets, hover, force-replacement detection | Product becomes a text editor |
| Provider source repositories | Mirrored documentation and examples | Hover loses prose; schema descriptions only |
| OpenTofu / Terraform | Execution | Product non-viable |
| MiniStack | Convergence testing | Headline feature lost |
| Docker or Podman | Running MiniStack | Convergence unavailable |
| Open Policy Agent, Checkov, Trivy | Policy and scanning | Substitutable |
| SQLite with FTS5 | Local index and search | Substitutable |
| AWS SDK (boto3) | Value completion, exposure analysis, drift | Differentiators lost |

---

## 16. Open Questions

| ID | Question | Owner | Needed by |
|---|---|---|---|
| OQ-1 | Internal tool or a product you intend to sell? Determines the weight of R-1 (BUSL) and whether Qt/GTK licensing or commercial support matters. | Sponsor | Immediately |
| OQ-2 | Is the v2 Hub a commitment or a maybe? If committed, DD-12's design obligations are requirements. If not, some v1 abstractions are waste. | Sponsor | Before P1 architecture |
| OQ-3 | Ubuntu only, or must Fedora/Arch/Debian be first-class? Affects packaging effort and GTK version assumptions. | Product | Before P5 |
| OQ-4 | Validate A-3 — will users have read describe access across the accounts they work in? If not, FR-SCH-11 is cut and the editor's differentiation narrows considerably. | Security | Before P3 |
| OQ-5 | Validate A-4 — who actually writes your Terraform? If it is exclusively a small expert team, guided authoring (P4) is low value and should be cut. | Product | Before P4 |
| OQ-6 | Spike required: is GtkSourceView 5 sufficient for the inline decoration density implied by FR-ED-05, or is a custom widget needed? This is the largest technical unknown in P1. | Engineering | P1 week 1 |
| OQ-7 | Which providers beyond `aws` are bundled at launch? Determines the size of the shipped schema and documentation set against NFR-03. | Product | Before P1 completion |
| OQ-8 | Reference hardware for NFR-01/02? The performance budgets need a defined machine. | Engineering | Before P1 |
| OQ-9 | Should the exposure analyser cover resources not managed by Terraform (imported, ClickOps, other tooling)? Improves accuracy, requires broader read access. | Security | Before P3 |
| OQ-10 | Does an internal module catalog already exist, and who owns curation? Without an owner, P4 has no content. | Platform | Before P4 |

---

## 17. Out of Scope for This Document

Technical architecture, data model, UI design, and go-to-market. These follow once §16 is closed.
