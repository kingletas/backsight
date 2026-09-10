# Theme tokens

`src/backsight/app/theme/tokens.py` is the source of truth and the one file in
the package allowed a literal colour. **Nothing is generated to disk.** The
`@define-color` block is built in memory by `tokens.define_colors(mode)` and
loaded from a string, so there is no `tokens.light.css` to regenerate and
nothing on disk to hand-edit by mistake.

The one thing that *is* written out is the editor's colour scheme, because
GtkSourceView loads a scheme from a path:

```bash
python -m backsight.app.theme.schemes     # writes theme/schemes/backsight-{light,dark}.xml
```

```python
from backsight.app.theme import Theme, tokens

Theme.shared()  # in do_startup, once per display
tokens.color("plan_replace")  # Gdk.RGBA, for anything that draws
```

`Theme` loads the token sheet for the current mode, reloads it on
`notify::dark`, then layers `components.css` on top at a higher priority and a
zoom sheet above that. Order matters: components reference the named colours,
and the zoom sheet overrides one declaration in them.

`components.css` is hand-written and contains no literal colours; a test fails
the build if one appears.

## The one idea

Colour encodes **consequence**, not category. Every coloured element in the app
resolves to one of four levels:

| Level | Means | Examples |
|---|---|---|
| safe | additive, reversible | new resources, tag changes, satisfied policy |
| disruptive | brief downtime, recoverable | in-place updates, drift, stale plan |
| irreversible | destroy or replace, no rollback | `aws_db_instance` replacement, bucket destroy |
| blocked | won't run | policy failure, missing backend, state lock held |

`accent_*` is the fifth family and is explicitly **not** a severity. It marks
the current file, selection, plan identifiers, and links. Never use it to say
something is fine — safe already means that.

Don't add a fifth severity. Six severities means nobody reads any of them.

## Treatment rules

These matter as much as the values; two things can share a hue and still be
distinguishable.

- **Blocked fills its card background. Irreversible only takes a border.** Both
  are red. The difference between "this is dangerous" and "this will not run"
  is carried by fill, not hue. `.tf-blocker` is the only element in the app
  allowed a full coloured background.
- **Apply is neutral until the plan contains an irreversible change.** Add
  `.tf-irreversible` to `button.tf-apply` from plan data. A permanently red
  Apply button trains people to ignore red.
- **One accent-filled button per screen.** Everything else is `.tf-quiet`.
- **Line washes colour the row background only.** Syntax colours stay intact
  inside the wash so code remains readable.
- **Annotations are sans, code is mono.** The interstitial line under an
  annotated statement is commentary about the code, not code.
- **Single-sided borders get `border-radius: 0`.** Rounded corners need a full
  border on all four sides; `RADIUS["flush"]` exists for this.
- **Never use opacity on text.** It multiplies against whatever is behind it and
  drifts per surface. Use `ink_muted` or `ink_faint`.

## Elevation

`canvas` → `surface` → `panel` → `overlay`, in that order, lightest last in
light mode and lightest last in dark mode too. Two floating layers maximum
(popover over panel). A third means it should have been a dialog.

Inset panels sit on `surface`, not `panel`, so they read as recessed rather
than as a card floating on a card.

## Type

Base 13px, editor 12.5px. Two weights only — 400 and 500. Anything at 600 or
above reads heavy against GTK chrome. Sentence case everywhere, including
buttons and headings. No terminal punctuation on labels; helper text and empty
states do take periods.

IBM Plex Sans and IBM Plex Mono share a skeleton, which keeps the tree and the
buffer feeling like one surface. Cantarell and a generic monospace are the
fallbacks, so the app degrades sanely on a system without Plex installed.

## Contrast

Every text-on-background pair in the palette was checked against WCAG AA at
small sizes and passes in both modes. `ink_faint` and `syn_comment` sit closest
to the line (4.68:1 light, 5.48:1 dark) — if either is darkened toward the
background for aesthetic reasons, re-run the check first:

```python
# ratio(ink_faint, surface) must stay >= 4.5
```

`check_parity()` raises if a token exists in one mode and not the other. It runs
on every generation, so a half-added token fails the build rather than
rendering as transparent black at runtime.

## Adwaita bridge

`ADWAITA_MAP` repoints libadwaita's own named colours at this palette so stock
widgets — headerbar, menus, switches, dialogs — inherit it instead of fighting
it. If a stock widget looks wrong, the fix is usually a missing entry there
rather than a new override in `components.css`.

Note that `warning_bg_color` and `success_bg_color` map to the *edge* stops,
not the tint stops, because Adwaita uses those as solid badge fills where the
pale tints would disappear.
