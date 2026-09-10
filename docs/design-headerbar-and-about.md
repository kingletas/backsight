# Header bar and About dialog

Two changes. They are independent — land them in either order.

Both consume the tokens in `theme/`. No literal colours in any new code; if a
value is missing, add it to `app/theme/tokens.py` in both palettes — `check_parity()`
refuses a token that exists in only one of them.

---

## 1. Remove the "Open workspace" button from the header bar

### What is wrong now

The button is styled as the window's primary action and pinned to the top-left,
permanently. It is only the primary action while no workspace is open, which is
a few seconds of the app's life. After that it is a large accent-filled button
occupying the position GNOME users read as back-navigation or sidebar toggle,
for an action performed maybe twice a week. On first launch it also duplicates
the empty state's own "Open workspace…" button, so the same action appears
twice on one screen.

### What replaces it

A workspace switcher set as the window's title widget. It shows where you are;
opening a different workspace becomes one row inside it.

```
Gtk.HeaderBar
├── pack_start: Gtk.ToggleButton  icon "sidebar-show-symbolic"   → toggles the tree
├── title_widget: Gtk.MenuButton  .tf-workspace-switcher
│     child: Gtk.Box (horizontal, 6px)
│       ├── Gtk.Label   workspace name        .tf-medium
│       ├── Gtk.Label   environment           .tf-chip .tf-disruptive
│       └── Gtk.Image   "pan-down-symbolic"
├── pack_end: Gtk.MenuButton      icon "open-menu-symbolic"      → app menu
├── pack_end: Gtk.Button          "Plan"      .tf-quiet
└── pack_end: Gtk.Label           branch name .tf-small .tf-dim
```

The environment chip takes its consequence class from the workspace, not a
fixed colour: `prod` → `.tf-disruptive`, everything else → no chip at all.
Don't invent a colour for `staging`; an uncoloured name is the neutral case.

### Popover contents

`Gtk.PopoverMenu` isn't flexible enough here — use a plain `Gtk.Popover`
containing a `Gtk.ListBox` with `selection-mode: none`.

Header row: "Open workspaces", `.tf-micro .tf-faint`.

One row per known workspace, each two lines:

- Line 1: workspace name. The current one gets `.tf-current` and a check icon.
- Line 2: `.tf-micro .tf-faint` — path, backend, state summary. The state
  summary uses the consequence vocabulary: `clean`, `3 drifted`
  (`.tf-drift`), `local state` (`.tf-nostate`).

Final row, separated by a `Gtk.Separator`: "Open workspace…" with a
`folder-open-symbolic` icon and the accelerator label `⌘O` (`Ctrl+O` on
non-Apple keyboards) right-aligned.

### Rules

- **Keep the `Ctrl+O` accelerator bound and working.** Removing the button must
  not remove the shortcut; the muscle memory has to survive.
- The switcher is **not** an accent-filled button. It is a quiet bordered
  control — `.tf-quiet` sizing, `RADIUS["control"]`.
- Recent workspaces persist in `GSettings` as a string array of paths, capped
  at eight. A path that no longer exists is shown once with `missing` in place
  of the backend line and removed on the next launch.
- When no workspace is open, the switcher label reads "No workspace" in
  `ink_muted` and the popover opens with only the "Open workspace…" row plus
  "Open example workspace". This is the **only** place the example lives once
  the empty state is revised — see below.

### While you are in this file

The empty state currently offers "Open workspace…" and "Open example
workspace" side by side as equals. They aren't equals: one is what a real user
does, the other is a demo. Keep "Open workspace…" as the single accent button
and demote the example to a text link beneath it.

---

## 2. Rebuild the About dialog

### What is wrong now

`AdwAboutDialog` with no installed app icon, so GTK falls back to the generic
document glyph — which reads as unfinished software. The version pill `0.0.0`
occupies the most prominent horizontal band in the dialog and communicates
nothing. The two action rows are "Details" and "Legal": one is a label that
describes nothing (every row is details) and the other is the least-clicked
thing in any about dialog, given half the action area.

Nowhere does the dialog say what Backsight is.

### Do not extend AdwAboutDialog

It owns its icon, version pill, and row structure, and sources most of it from
appstream metainfo. It can't produce this layout. Build a `AdwDialog`
subclass, `BacksightAboutDialog`, 340px content width.

Keep `AdwAboutDialog` — construct it lazily behind the "Credits and legal" row,
where its licence rendering and credits handling are worth having.

### Structure

```
AdwDialog  (content_width: 340)
└── AdwToolbarView
    ├── top bar: AdwHeaderBar (show_title: false, flat)
    └── content: Gtk.Box (vertical, 0)
        ├── identity block          padding 22px 20px 16px, centred
        │     ├── Gtk.Image         backsight icon, 56px
        │     ├── Gtk.Label         "Backsight"          .tf-title
        │     └── Gtk.Label         description, wrapped .tf-dim
        ├── AdwPreferencesGroup     build facts
        └── AdwPreferencesGroup     actions
```

Description string, verbatim:

> Reads your state and your plan, and tells you what a change will actually
> cost before you run it.

### Build facts group — `AdwActionRow` each, value in the suffix

| Row | Value | Source |
|---|---|---|
| Version | `0.4.1 · 8f2a41c` | app version + short git SHA baked at build |
| Terraform | `1.9.8 detected` | `terraform version -json`, resolved at startup |
| Tested against | `1.6 – 1.9` | constant in the build |

Suffix labels are mono (`.tf-mono .tf-small`). If the Terraform binary isn't
found, the value reads `not found` in `.tf-nostate` — don't hide the row. The
absence is the useful information.

These three exist because the first three questions on any bug report against
an infra tool are which build, which Terraform, and whether that combination is
supported. One screenshot should answer all three.

### Actions group — `AdwActionRow`, activatable

| Row | Icon | Behaviour |
|---|---|---|
| What's new in 0.4 | `sparkle-symbolic` | navigates to a release-notes page in the same dialog |
| Keyboard shortcuts | `keyboard-symbolic` | closes, opens the shortcuts window; suffix shows `⌘?` |
| Report an issue | `bug-symbolic` | opens the issue tracker externally, with version and Terraform version prefilled in the URL |
| Credits and legal | `license-symbolic` | presents `AdwAboutDialog` |

Footer, below the groups, `.tf-micro .tf-faint`, centred, wrapped:

> A backsight is the reading a surveyor takes back to a known point, to
> establish where they are before measuring forward.

This isn't decoration. It is the only place the product explains its own
premise, and the premise is the reason to prefer this over a terminal.

---

## 3. Install the icon

`data/icons/backsight.svg` and `data/icons/backsight-symbolic.svg` are in this
repo. Install them so GTK stops falling back to the document glyph:

```
data/icons/hicolor/scalable/apps/dev.backsight.Backsight.svg
data/icons/hicolor/symbolic/apps/dev.backsight.Backsight-symbolic.svg
```

The app ID must match the filename or the icon won't resolve. Set
`Gtk.Window.set_default_icon_name()` to the same string, and reference it in the
`.desktop` file and the appstream metainfo.

The mark is a surveyor's benchmark: ring, crosshair, and the triangle marking a
fixed station. It is four paths and holds together at 16px, which it needs to,
because it is also the window icon and the dock tile.

---

## Acceptance

- No accent-filled button remains in the header bar in any state.
- `Ctrl+O` opens a workspace with the header bar button gone.
- Switching workspaces from the popover doesn't lose unsaved buffers — prompt
  first, in the same style as the apply gate: name the consequence, then act.
- The About dialog shows a real icon, not the document fallback.
- With no Terraform binary on PATH, the About dialog still opens and the
  Terraform row reads `not found`.
- Every colour in the new code resolves to a token in `theme/tokens.py`.
- `check_parity()` passes, and `python -m backsight.app.theme.schemes` rewrites the
  two editor schemes from the same tokens.
