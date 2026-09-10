# 113 of 138 menu actions reach nothing

Measured by asking the window itself which actions it has registered, rather
than by reading the list of names the architecture test maintained by hand.

| | Count |
|---|---:|
| Actions named in a menu, not marked blocked | 138 |
| Registered on the window | 12 |
| Dispatched as a line operation | 13 |
| **Reaching nothing at all** | **113** |

Wiring the obvious half brought it to **81**: the panel toggles, the annotation
layers, the tab-closing group, the clipboard and undo, copy-path, the colour
scheme override, plan, close, full screen and go-to-line. Every one of those
was a feature that already existed and couldn't be reached from the menu that
named it.

## Why the existing test did not catch it

`test_every_item_resolves_to_a_command_or_is_a_submenu` checks each action name
against a set written in the test file. That set says a name is *intended*. It
can't say the name *works*, and every one of the 113 passed it.

Four annotation toggles — gutter verdicts, inline explanations, code lens,
resolved values — sat in the View menu wired to nothing at all. Choosing one
did nothing, silently, and sheet 9 specifies that each layer toggles
independently.

## Two different problems inside the 113

Some are genuinely unbuilt: `blame`, `scaffold`, `show-state`. Those are honest
gaps and the menu greys the ones that are known-impossible already.

The rest are **built but named differently**. The window registers panel
visibility as one parameterised `panel` action; the menu names
`toggle-left-rail`, `toggle-right-rail`, `toggle-plan-drawer`. Both work; they
aren't the same string, so nothing joins them up. That is the more dangerous
half, because the feature exists and the menu still can't reach it.

## What now holds the line

The unwired set is checked into `tests/architecture/test_menus.py` and the test
asserts the current list **exactly**. Adding a menu item that goes nowhere
fails; so does wiring one without removing it from the list. The number can only
go down, and it goes down deliberately.

It went on down: the find row (**77**), file operations, tab operations,
navigation and conversions (**31**), git (**24**), workspace search, snippets
and the clipboard ring (**15**), state, provider docs, compare and the activity
log (**10**), and the findings group (**5**).

**Five remain, and none of them is wiring.**

- **`split-right`, `split-down` and `clone-into-split`** need a split view. The
  editor holds one `Adw.TabView`; a split is a `Gtk.Paned` of two, with the
  active one tracked by focus, and every method that touches `self._tabs` has
  to learn which. That is a feature, not a connection.
- **`generate-import-block`** needs the import ID format for a resource type,
  which is provider knowledge the schema doesn't carry.
- **`exclude-from-plan`** has no concept behind it. Nothing in the MVP knows
  what it would mean to plan a workspace with a file left out.

Each is written down here so it stays a decision rather than becoming an
oversight.
