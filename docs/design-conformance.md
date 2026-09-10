# Conformance to design v2 — what is done, and how to do the rest

**Read this with `docs/findings/`.** Every claim below that something cannot be
done points at a finding with the measurement in it. Nothing here is inferred
from a filename or from a stylesheet: where a number appears, it was measured on
a presented window or in a rendered screenshot.

## Closed

| Was | Now |
|---|---|
| Two token scales, nothing comparing them | One scale, and `tests/architecture/test_the_geometry_is_on_the_scale.py` fails on drift in either direction |
| Fifteen paddings on neither scale | All on the scale, and the same test refuses a new one |
| The run control never carried consequence and was never absent | Takes the irreversible fill from the plan; leaves the header when no plan can run |
| No way to intervene in an apply | *Stop after this resource* — one SIGINT, which is what the engine reads as a graceful shutdown |
| One aggregate elapsed time | Per resource, tabular, blank until a resource starts |
| Five palette prefixes | Six — `!` lists what is stopping the plan and jumps to its line |
| Consequence groups were bordered cards | A 2px rule down the left edge, uppercase micro label |
| Drawer capped at 45%, no default height | Opens at 38%, content stops at 45%, a drag reaches 70% |
| Four outcomes in one green after an apply | Each takes its own consequence colour; the icon still separates failure by shape |
| Code row 23px against an arithmetic of 16 | 16px — see [019](findings/019-line-height-and-em-sizing-meet-the-desktop.md) |
| *Raw output* | *Show the original* |
| The tab said *Public access*, the chip said *exposure* | **Exposure**, everywhere. The menu keeps *Analyse public access* because that phrase is how somebody who has never met the word finds it |
| 68 comments citing a design of twelve sheets | Gone. The reason stayed; the dead pointer went |

## Open, with the way to do it

### 1. The tab strip is 41px and the design says 28

**Do not attempt this as part of a visual sweep.** →
[017](findings/017-the-tab-strip-has-a-floor-of-41px.md) for the measurements.

Six pixels were recovered by styling. The remaining thirteen, the `+` after the
last tab, and the dirty dot replacing the close button are one decision: keep
`Adw.TabBar`, or build the strip.

**If you build it:**

1. Keep `Adw.TabView`. It is the model — pages, selection, close — and none of
   this is about the view.
2. Replace `Adw.TabBar` with a `Gtk.Box` of `Gtk.ToggleButton`s bound to
   `TabView.get_pages()`, a `Gtk.SelectionModel`. One button per page, its
   `active` following `selected-page`.
3. Draw the row from `ROW["tab"]`, so the token is the thing the strip is built
   from rather than a constant nothing reads.
4. Put the `+` in the same box, after the last button.
5. The dirty dot and the close button share one 14px slot: show the dot while
   `page.get_child()` is modified, the close button on hover, and never both.
6. **Re-wire four things that go through `Adw.TabBar` today**, all named in
   `engine/layout/mouse.py`:
   - the tab context menu and middle-click-close, which hit-test by walking
     the bar's widgets in `editor.py` — a real button makes both trivial
   - drag to reorder — `Gtk.DragSource` plus a drop target per button
   - drag out to split — the same source, dropped on the editor
   - `Adw.TabOverview` — it is fed by the bar and would have to go or be
     driven by hand
7. Update `tests/layout/test_mouse_inventory.py`: every entry names the symbol
   that handles it, and four of those symbols move.

**Budget it as days, not as an afternoon**, and take it on its own branch. The
four behaviours in step 6 all work today.

### 2. The design guide needs five amendments

These are the places where the guide and the shipped application disagree and
**the application is right**. Each needs one sentence from whoever owns the
design:

| Where | What it should say |
|---|---|
| *Tabs* | The strip is **41px**. 28 is not reachable with `Adw.TabBar`; the cost of the rest is in finding 017 |
| *Foundations* | Sizes are **ratios of the desktop body size**, and the pixel figures hold at a 13px base. On this machine the code face renders at 11.2px |
| *Drawer* | **Two ceilings**: content stops growing at 45%, a deliberate drag reaches 70%. One number could not carry both meanings |
| *Apply — three endings* | **Consequence colour survives the apply.** A destroy that succeeded is still the row somebody is scanning to find |
| *Drawer tabs* | **Ten**, not eight. Docs, Git and Output are real surfaces the guide did not enumerate, and the rule against hiding a tab is what puts them there |

### 3. `UAT.md` case 7.1 contradicts a shipped and tested behaviour

UAT 7.1 presumes four opens make four tabs. The project ruled that an ordinary
open reuses the tab in front, and `tests/acceptance/test_opening_replaces.py`
asserts it.

**The acceptance document contains a case the build is designed to fail.**
Somebody driving UAT end to end records a failure that is a specification
conflict. Amend 7.1 to the shipped model, or reverse the ruling — but not
neither, because today the document cannot be run honestly.

### 4. The review row is stacked, and the design puts it on one line

The design asks for `glyph · address · location · reason · cost` on one row.
It ships as three or four stacked lines, and **location and cost are both
carried** — an earlier audit read a fixture that had neither and recorded them
as missing.

Left as it is, and the reason is width: the drawer is about 1020px with the
rail open, and the reason is a sentence. On one line, the sentence is what gets
truncated, and it is the part that says *why*. **If you change it, check it at
a 1280px window with the rail open** rather than at full screen.

### 5. Both design typefaces

`fonts-jetbrains-mono` is installed and is what the code renders in.
**`fonts-ibm-plex` is not**, so every interface label falls back to Cantarell
and no claim about the sans is verified.

```bash
sudo apt install fonts-ibm-plex
```

Then re-take the smoke set and compare. Nothing in this repository can install
it.

## Declared toolkit limits

Five, each with a finding rather than a note in one module's docstring:

| Wanted | Finding |
|---|---|
| Multiple cursors, column selection, code folding | [002](findings/002-three-baseline-capabilities-have-no-api.md) |
| Indent guides | [016](findings/016-indent-guides-have-no-api-either.md) |
| 28px tab strip, `+` after the last tab, dot replacing close | [017](findings/017-the-tab-strip-has-a-floor-of-41px.md) |
| A one-pixel occurrence outline | [018](findings/018-the-occurrence-outline-is-an-underline.md) |
| `line-height` meaning what it means on the web | [019](findings/019-line-height-and-em-sizing-meet-the-desktop.md) |

Tab edge bars for plan impact and git state, and `Ctrl+K` chords, are declared
in the implementation record: `Adw.TabPage` is not a widget, and GTK has no
chord parser.
