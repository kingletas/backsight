# From nothing to a working Backsight

By the end of this you will have Backsight open, a plan drawn onto a real file,
and a sense of what it is telling you. It takes about ten minutes, and nothing
here touches a cloud account.

## Contents

- [What this is](#what-this-is)
- [Step 1: install what it needs](#step-1-install-what-it-needs)
- [Step 2: open the example that plans offline](#step-2-open-the-example-that-plans-offline)
- [Step 3: plan it, and read what you see](#step-3-plan-it-and-read-what-you-see)
- [Step 4: point it at your own Terraform](#step-4-point-it-at-your-own-terraform)
- [What you get without asking](#what-you-get-without-asking)
- [Where to go next](#where-to-go-next)

## What this is

Backsight is a Terraform editor for Linux that shows what a change will do —
what it creates, changes, replaces or destroys — beside the line that causes
it, while you are still writing.

The problem it answers: in an ordinary editor you find out what your Terraform
does only after you commit, push and wait for CI. Renaming a resource looks
harmless in the file and is a destroy-and-recreate to Terraform, and nothing
warns you until the plan output scrolls past.

## Step 1: install what it needs

**The GTK 4 bindings**, which Backsight is drawn with:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gtksource-5
```

**OpenTofu or Terraform on your `PATH`.** Backsight runs the one it finds; it
never downloads one. OpenTofu's install page is
<https://opentofu.org/docs/intro/install/>. Check it is there:

```bash
tofu version
```

**The two typefaces it is drawn in.** Optional — without them it falls back to
the desktop's fonts, and Preferences tells you so:

```bash
sudo apt install fonts-ibm-plex fonts-jetbrains-mono
```

**`uv`**, which builds the environment Backsight runs in. Its install page is
<https://docs.astral.sh/uv/getting-started/installation/>. Check it is there:

```bash
uv --version
```

**Then the application itself**, run from its own checkout:

```bash
git clone https://github.com/kingletas/backsight && cd backsight
```

The first `make` builds a virtualenv that can see the system's GTK bindings.
That takes a minute once and not again.

## Step 2: open the example that plans offline

The repository carries a workspace built for exactly this: two resources of
Terraform's own `terraform_data` type, so it needs no provider, no credentials
and no network.

```bash
make app WORKSPACE=fixtures/plannable
```

The window opens with the files of that workspace in the rail on the left.

**One click on a file previews it** — it shows in the editor, and the next file
you click replaces it, so looking around doesn't leave a tab per file. **Two
clicks open it for good.** Open `main.tf`.

> [!tip] If the window says the engine is missing
> Backsight looked for `tofu` and didn't find it. Everything except planning
> still works. Install OpenTofu, or name a different binary — `terraform`, say —
> in **Preferences → Terraform**.

## Step 3: plan it, and read what you see

Press **Ctrl+Return**. Saving the file does the same thing: a plan runs on every
save unless you turn that off in Preferences.

Within a few seconds you should see:

- **A `＋` in the gutter** beside each of the two `resource` blocks, and a green
  bar running down each block. That is the plan saying *this will be created*.
- **`Add` at the right end of the line**, in the same row as the code. Nothing
  the plan says ever pushes your code down a line.
- **The bar along the bottom** reading `＋2` — the whole plan in one glance.
- **The Changes drawer**, headed `2 to add`.

Colour means consequence and nothing else: green is safe, amber changes
something in place, red can't be undone. The **Plan** button in the top right
turns red on its own when the plan destroys or replaces anything, so the
control you are about to press already tells you what it will do.

**Nothing has been applied.** Applying is a separate button in the drawer, and
for anything irreversible it asks you to type the workspace's name first.

## Step 4: point it at your own Terraform

```bash
make app WORKSPACE=~/path/to/your/terraform
```

Any directory works — one root module, or a repository of many. The rail shows
its top level and nothing more until you open a folder.

Planning your own code needs whatever that code needs: a provider,
credentials, a backend. **Backsight never stores, shows or logs a credential.**
It uses whatever your shell already has, and a separate profile for applying if
you set one.

## What you get without asking

- **The plan on the line that causes it**, rather than in a terminal you have
  to match back to the file.
- **Replacements called out**, with the attribute that forced them.
- **An apply screen that reads the state back afterwards** and says whether
  what happened is what the plan said would.
- **A stop button while an apply runs**, which lets the resource in flight
  finish and starts nothing further.
- **Drift** — what changed outside Terraform — from a check that changes
  nothing.
- **A library of snippets and examples**, `Ctrl+E` to find one.

## Where to go next

- [README](../README.md) — what works today, and what it deliberately doesn't do
- [docs/design-conformance.md](design-conformance.md) — what is built, and how to build the rest
- [CONTRIBUTING.md](../CONTRIBUTING.md) — the shape a change should arrive in
