# 002 — Chrome follows the desktop; meaning is ours

**Decided 2026-09-07. The accent clause is superseded by [003](003-the-accent-is-pinned-and-002-is-narrowed.md); everything else stands.**

## What was chosen

Two kinds of colour, in one module.

**The desktop decides the chrome.** Window, view, header bar, sidebar, borders and text come from libadwaita's named colours. The application matches the system theme and the user's chosen accent without being configured. On the machine this was built on, that accent is a red — not the blue in the design sheet — and that is correct.

**We decide meaning.** Create, change and destroy are pinned in both schemes and never move with somebody's accent, because they carry information rather than taste.

Backgrounds are `alpha()` over whatever the view is, so a tint survives both schemes by construction rather than by having been checked in each.

## What else was considered

Pinning every token to the hex values in sheet 3's table. Rejected: it makes a user with a purple desktop run a blue application, which contradicts the sheet's own first theming rule — *follow the desktop*. The sheet's chrome values turn out to be Adwaita's anyway, so following the desktop produces them for anyone on the default theme and something better for anyone who is not.

## The rule that has teeth

**No colour literal outside `app/theme/tokens.py`.** `tests/architecture/test_no_colour_outside_the_theme.py` fails the build on a hex or an `rgba(...)` anywhere else under `app/`, and separately asserts the theme module does contain colours — a rule nothing violates because nothing is coloured is not a rule.

## What this cost, once, immediately

The vocabulary nearly split. The rest of the application says `add`, `change`, `replace`, `destroy`; the first version of this module said `create`, `update`, `destroy`. Nothing matched, every band rendered untinted, and every test passed. There is now a test asserting every word `presentation.ACTIONS` uses has a colour.
