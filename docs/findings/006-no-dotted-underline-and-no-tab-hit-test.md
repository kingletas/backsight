# Two of sheet five's mouse details have no toolkit support

Measured against GTK 4.14 and libadwaita 1.5.0.

## GTK CSS has no dotted underline

Sheet 5 marks a clickable status segment with a dotted underline — the
convention that says *this reacts, but it is not a link*. GTK's CSS parser
rejects both spellings:

| Rule | Result |
|---|---|
| `text-decoration: underline dotted` | `"dotted" is not a valid color name` |
| `text-decoration-line: underline; text-decoration-style: dotted` | `unknown text decoration style value` |
| `text-decoration: underline` | accepted |

Pango's underline styles are `SINGLE`, `DOUBLE`, `LOW` and `ERROR` (a squiggle);
none is dotted either. **A plain underline is the closest thing that exists**,
and it is what ships. The affordance survives; the distinction between "link"
and "reacts" does not, and no amount of care in our code recovers it.

**This was in the tree as a comment claiming a dotted underline while the rule
it referred to failed to parse**, printing a theme parser error on every start.
The comment was written from the sheet rather than from anything that ran.

## The tab bar cannot be asked which tab is under the pointer

`Adw.TabBar` has no hit-test, and `Adw.TabPage` is not a widget. Walking the
bar's children finds `AdwTabBox` holding one `AdwGizmo` per tab — with no
label, no tooltip and no page reference on any of them.

The gizmos are laid out in page order, so the *n*th gizmo is the *n*th page.
That is libadwaita's internal layout and it may change in any release, so it is
used with a guard: **if the number of gizmos does not match the number of
pages, middle-click does nothing.** A version that reshuffles the box makes the
feature stop working, which is survivable. Closing the wrong file is not.
