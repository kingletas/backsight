# Finding 017 — the tab strip has a floor of 41px, and 28 is not reachable by styling

**Status: measured, 2026-09-10 — six pixels recovered, thirteen unreachable, and the way to the rest costs five features.**

## What the design asks for

A **28px** tab strip: flat, one-pixel separators, the active tab drawn on the
buffer surface with a 2px accent on its top edge and no side or bottom border.
The headline claim the redesign rests on is chrome falling from 92px to 64px,
and nineteen pixels of tab strip is a third of that saving.

## What it measures

`Adw.TabBar`, styled as far as CSS will go:

| | Before | After | Design |
|---|---:|---:|---:|
| Strip | 47px | **41px** | 28px |
| `AdwTab` | 34px | **34px** | — |

The six pixels came off the bar and the box. **`AdwTab` did not move at all.**

## Why the tab will not move

`AdwTab` computes its own minimum in C. Its measured minimum is 34px with the
label, the close button and the indicator inside it, and **a `min-height` of
10px at `GTK_STYLE_PROVIDER_PRIORITY_USER` — the top of the cascade, above the
application sheet and above the theme — changes nothing.** The same is true of
the close button, which stays at 24px against an 18px rule, and of the icon,
which ignores `-gtk-icon-size`.

This was checked by measuring, not by reading: a probe sheet was installed at
USER priority on a presented window and every node re-measured.

```
tabbar tabbox > tab button.tab-close-button { min-height: 10px; }   → 24px
tabbar tabbox > tab { min-height: 10px; padding: 0 8px; }           → 34px
tabbar tabbox { padding: 0; }                                       → 41px
```

**A stylesheet cannot reach a measurement made in C.** That is the finding.

## Two more of the design's tab requirements come from the same place

Checked against the installed libadwaita 1.5, property by property:

| Wanted | Why it cannot be done |
|---|---|
| **The `+` sits after the last tab, never elsewhere** | `Adw.TabBar` has exactly two slots — `set_start_action_widget` and `set_end_action_widget`. There is no slot after the last tab, and the tab box is built from the view's pages. Ours is at the end of the strip. |
| **The dirty dot replaces the close button in the same 14px** | `Adw.TabPage` exposes `indicator-icon` and nothing that hides or replaces the close button. So the dot takes the indicator slot and the close button stays beside it — which is also the slot the plan-impact mark wants. |

**These are not three problems. They are one decision**, and it is the same
decision as the height: keep `Adw.TabBar`, or build the strip.

## What the remaining thirteen pixels cost

The only route to 28px is a tab strip of our own — a `Gtk.Box` of buttons over
the `Adw.TabView`, with `Adw.TabBar` removed. That buys the height, the flat
separators, the accent top edge, the dirty dot replacing the close button, the
italic preview label and both edge bars. It costs:

| Lost | Why |
|---|---|
| Drag to reorder | `Adw.TabBar` provides it; a hand-built strip does not |
| Drag out to split | same |
| `Adw.TabOverview` | it is fed by the bar |
| The tab context menu | `editor.py` hit-tests tabs by walking the bar's own widgets, because `Adw.TabPage` is not one |
| Middle-click closes | the same hit-test path |

The last two are wired and inventoried in `engine/layout/mouse.py`, and every
one of the five is a thing somebody uses.

## The decision

**Not taken here.** Six pixels are recovered and kept; the thirteen remaining
are declared rather than bought, because a visual sweep is the wrong moment to
trade five working behaviours for them. `docs/design-system.md` carries the
guide for building the in-house strip when somebody decides the height is worth
more than the five.

**The design guide should record 41px as the shipped figure**, so the next
reader is not measuring a gap that has already been investigated.
