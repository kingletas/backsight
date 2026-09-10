# The tests and the smoke were running on the developer's own desktop

## What was happening

The smoke drives a real window through two dozen views, presenting it, opening
dialogs and a palette. `make smoke` ran it on whatever `DISPLAY` was set —
which is the screen the developer is working on. Windows appeared over their
work, took focus, and took the pointer with them.

The test suite was worse, because it looked innocent. Constructing a window
doesn't map it, so for a long time nothing appeared. Then
`test_every_action_activates` began activating **every** action, and several of
them present a dialog: rename, delete, discard, move, suppress, About. A test
run started throwing dialogs onto the screen.

## The lesson, which is the reason this is written down

**The gate was killed twice mid-run with SIGKILL, and the first explanation was
memory.** The machine was genuinely short of memory, so the explanation fitted
— and it was wrong. Keystrokes typed at the desk were landing in windows the
test run had opened.

Two things to take from it. **A plausible cause that fits the evidence isn't
the cause**, and "the machine is short of memory" is exactly the sort of
explanation that ends an investigation early because it feels sufficient. And
**the question only arose because of a defect** — the windows should never have
been on the developer's screen, so the interference wasn't an environmental
fact to explain but a bug to fix.

## What it is now

`backsight.app.offscreen` starts an `Xvfb` on a display in the 90–129 range and
points `DISPLAY` at it. Both the suite's root `conftest.py` and the smoke call
it **before anything imports `gi`**, because GTK connects to a display when it
is initialised and by then the choice is made.

`:0` and `:1` are excluded by construction rather than by luck. The server is
registered with `atexit`, so a crashing run doesn't leak one. With no `Xvfb`
installed nothing is changed and the caller is told so, rather than failing.

`BACKSIGHT_DISPLAY` overrides it, which is how somebody watches the smoke run:
`make smoke-watch` sets it to the current display.

Minimising the windows was the obvious answer and the wrong one — it treats
being on the screen as acceptable as long as it is small.

## A private display does not contain everything

Windows kept appearing, twice, after the private display was in place, and the
first explanation was wrong both times.

**`Gtk.FileDialog` doesn't draw a window in this process.** It asks
`xdg-desktop-portal` in the desktop session to show a file chooser, and
`Gio.AppInfo.launch*` starts the file manager or terminal the same way.
Neither is on our `DISPLAY`. No X server we start can contain them, and there
is no display setting that prevents it. `open-workspace` was in the action
sweep, so a test run opened a file chooser on the desktop.

The general shape: **a private display contains what this process draws, and
nothing it delegates.** Anything that goes through the portal or D-Bus arrives
in the session the developer is using.

Those five actions are excluded from the sweep — and because `open-workspace`
is the exact bug the sweep was written to catch, they keep their cover through
a separate test that replaces the portal and checks only that the handler is
reached.

**And the SIGKILLs came from the desk.** The memory peak was 674 MB against
8 GB free. Windows a test run had put on the screen were being closed by hand,
which is also why the run died at a different point each time.

## The other half: the fallback was the desktop

`use_a_private_display` returned `None` when it couldn't start a server, and
the caller carried on with whatever `DISPLAY` already said. That is the exact
failure this module exists to prevent, arriving quietly through its own error
path. It raises `NoPrivateDisplay` now: a run that can't be contained should
not happen at all.

## And the private display was never used at all

Windows kept appearing a third time. The reason is the one that makes the
previous two look like guesses, because it means none of the containment had
ever worked:

**The desktop runs Wayland.** `GDK_BACKEND=wayland` is set in the session, and
GTK4 prefers Wayland whenever `WAYLAND_DISPLAY` is present. `DISPLAY` is then
simply ignored. Every window went to the desktop's compositor while a private X
server sat running and empty beside it.

It also explains why looking for the intruder found nothing. `wmctrl` and
`xdotool` are X11 clients: they can't see Wayland windows, so a watcher polling
`DISPLAY=:0` during a full test run reported a clean screen while windows were
opening on it.

`use_a_private_display` now sets `GDK_BACKEND=x11` and removes
`WAYLAND_DISPLAY` as well as setting `DISPLAY`, and a test asks the toolkit
which display it actually connected to rather than reading the environment
back. It runs in a subprocess, because `gtk_init` happens once per process.

**The lesson is the same one, for the third time.** Setting `DISPLAY` looked
like it worked: the server started, the number came back, the smoke printed
"on :90". Every observable said yes and the thing itself was untouched. What
was missing was one question — *did the toolkit connect to it* — and asking it
costs one line.
