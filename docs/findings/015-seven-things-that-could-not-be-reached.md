# 015 — Seven things that were built and could not be reached

Found by opening the application and using it, after the stacks window turned
out to lock it. Every one of these passed its own tests.

## What was wrong

**Seven of the drawer's nine tabs couldn't be clicked.** The `Esc to close`
hint was `hexpand=True` next to the tab strip, which also expands, so GTK split
the header evenly and gave 331px to twelve characters. The strip needs 1198px
and had 327px. Choosing a tab by key or palette never scrolled it into view
either, so the Library panel was read with `Changes` lit.

**The documentation panel told you to press a button it didn't have.** The
empty state said *press the button*; the only button in the panel appears after
a page has already loaded.

**Push was offered where there was no repository.** The gate existed —
`set_sensitive(not working.unreadable)` — and nothing called it: not opening a
workspace, not opening the tab. The button was live on a blank window. Pressing
it asked *"Push this branch?"* about a branch that didn't exist, warned that
other people could pull your commits, and returned `fatal: not a git repository`.

**A narrow window clipped instead of folding.** The panes are correctly told not
to crush their children, so below about 810px the window was simply narrower
than its own minimum and GTK clipped: at 630px the inspector's text ran off the
right edge of the screen. Nothing put a panel away when the room ran out.

**The tests panel couldn't run a test.** `TestPanel` takes an `on_run`; the
window built it as `TestPanel()`. Both halves worked and nothing joined them.

**Two empty states named an action and didn't offer it** — Tests and Drift.
This is what the stacks view was fixed for, in two more places.

**A label read `Save to plan plannable`**, which parses as nothing.

## What was done

The hint no longer expands, and the switcher scrolls the open tab into view —
including after layout, because doing it only on selection ran before the
scroller had a width to scroll within.

`Working.can_push` says a push needs a branch, no read error and no detached
head. An empty `Working` — what a window holds before anything has looked — is
now refused rather than permitted, and the panel refreshes when a workspace
opens and when the tab is shown.

Two breakpoints fold the inspector below 830px and the tree below 500px. Those
numbers are measured rather than chosen: the tree asks for 240, the editor 250
and the inspector 320. The first guesses were 1000 and 760, which put the
inspector away at widths it fitted in perfectly well and broke a test that was
right.

Folded panels are tracked apart from the layout, so widening restores exactly
what was showing and never re-opens something somebody put away.

## What it says about the tests

Each defect had a green suite. The pattern in all seven is the same one this
project keeps finding: **the parts work and the route between them doesn't.**

`tests/architecture/test_panel_callbacks_are_wired.py` is the general form —
every `Callable` a panel accepts must be passed something. It catches the tests
panel directly.

The first guard written for the folding looked for `add_breakpoint(` in the
source. It passed with the wiring deleted, because the method holding that call
was still there and nothing reached it — the defect being guarded against,
written into its own guard. It parses the constructor now.
