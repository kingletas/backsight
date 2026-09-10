# Why Backsight exists

**Because writing Terraform has no feedback loop shorter than a full CI run, and one of the mistakes it lets you make is deleting a production database by renaming a variable.**

## The problem

**Authoring is blind.** You write HCL. You can't see what it will do, what it will cost, whether it passes policy, or whether it exposes anything — until after commit, push, pull request and wait. Tens of minutes per answer turns writing infrastructure into guess-and-check, and code written that way is shaped by copying whatever module was nearest.

**The sharpest case is a rename.** You see a rename. Terraform sees a destroy and a create. Nothing in a general-purpose editor warns you, and the first time you find out is in a plan you are reading at the end of the loop, if you read it carefully.

**Failure also surfaces late.** Configurations that pass `validate` and `plan` still fail during apply — dependency ordering, semantically invalid IAM documents, `for_each` expanding against real data — and the blast radius of that is a half-applied state file.

## Why not VS Code and the Terraform extension

It gives syntax highlighting and schema completion, and stops there, because everything else needs context an editor doesn't have:

- It doesn't know your account, so it can't complete a real subnet id.
- It doesn't know your policy, so it will suggest an instance type your organisation forbids.
- It doesn't know your state, your costs, your module catalog, or what your change will expose.

Every one of those is knowable. None of it is surfaced at the moment it would change what you type, which is the only moment it is worth anything.

## Why not a security scanner

Because scanners answer a different question than the one being asked. The question is *"does this let anyone on the internet reach our database"*. A scanner answers *"is this rule `0.0.0.0/0`"*.

They evaluate resources in isolation, so exposure that emerges from a combination — a security group, a subnet, a route table and a gateway — is invisible to them, especially when some of those already exist and aren't in the diff.

## Why a desktop application

The first drafts of these requirements described a self-hosted server, and the form factor changed deliberately.

The value is in the authoring loop, and the authoring loop happens on a laptop. A server puts a network round trip between a keystroke and its consequence, needs credentials stored somewhere to be useful, and is a team deployment before it is a tool. **A workbench you install in one command and use on a plane is a different product**, and it is the one that closes the loop this exists to close.

Team governance — approvals, enforcement, shared policy — was deferred to a companion service rather than dropped, and the architecture is built so that service attaches without rework.

## What the reason decided

- **A plan beside your code**, run as you save or on demand, showing what would be created, changed, destroyed, and what forces a replacement.
- **Force-replacement comes from the plan, not the provider schema.** The schema simply doesn't carry the fact — see [decision 001](decisions/001-force-replacement-comes-from-the-plan.md). It arrives when the speculative plan lands rather than at the keystroke, and the interface says where the answer came from.
- **An unknown value says nothing rather than guessing.** An attribute whose default we can't read shows no default. Inventing `false` because most booleans default to false is how a workbench teaches somebody something untrue.
- **Round-trip safety is absolute.** The editor hands your file back byte for byte. A verdict is drawn as an overlay on the text view; a row inserted into the buffer would become a line of your file.
- **No browser engine, no JVM, no stored cloud credentials.** GTK 4 and Python, starting in under two seconds, working offline.

> **Early, and not released.** Version `0.0.0`. Read this as the reason something is being built in the open, not as a description of a finished thing.

## Where the name came from

**A backsight is the reading a surveyor takes back to a known point, to establish where they are before measuring forward.**

That is the premise of the application, and it is the reason to prefer it over a terminal. You can't know what a change does without first knowing, precisely, where you are standing — which state, which account, which resources already exist. A plan read at the end of a CI run is a measurement taken forward with no backsight behind it.
