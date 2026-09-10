# Toolkit notes

What was verified against the installed toolkit rather than remembered. Add to this whenever a lookup costs you more than a minute, so the next person doesn't pay for it twice.

Installed here: GTK 4.14.5, libadwaita 1.5.0, GtkSourceView 5.12.0, PyGObject 3.48.2, on Python 3.12.3.

## Things that fail differently than you expect

**`get_iter_at_line` returns a result tuple, not an iterator.** It is `(True, iter=<Gtk.TextIter>)`, so you want `.iter` or `[1]`. Written as if it returned the iterator, it fails with `'_ResultTuple' object has no attribute ...` far from the line that is actually wrong. The same shape applies to the other `get_iter_at_*` calls.

**A gutter renderer is a `Gtk.Widget` now.** `GtkSource.GutterRendererText` has no `set_size()`; it takes `set_size_request()`, `set_xpad()` and the ordinary widget properties. Anything you remember about sizing a renderer is GTK3.

**`query-data` carries the line number.** The handler signature is `(renderer, lines, line)`. `GtkSource.GutterLines` is the batch being drawn, so asking it for "the" line gives you the wrong answer for every row but one.

**There is no `Gtk.MainContext`.** It is `GLib.MainContext.default()`.

## Things that are already there

**GtkSourceView 5.12 ships a `terraform` language definition.** `LanguageManager.get_default().get_language("terraform")` returns it, and it highlights the sample in `spikes/sourceview_decoration.py` correctly. Check how far it goes before writing an HCL2 definition from scratch for the editor — the task may be smaller than it looks, or may only need extending.

**`Gtk.TextView.add_overlay(child, x, y)` places a widget in buffer coordinates**, and `move_overlay` repositions it. It scrolls with the text on its own; no scroll handler is needed.

**`pixels-below-lines` is a `Gtk.TextTag` property**, so vertical space can be reserved under one line without putting a character in the buffer.

## Provider schema output

**A schema has no provider version in it.** The keys of `provider_schemas` are bare addresses like `registry.opentofu.org/hashicorp/aws`. The version has to be supplied by whoever captured it, which in a workspace means the lock file.

**`resource_schemas[type].version` isn't the provider version.** It is the state schema version, an integer the provider bumps when it needs to migrate existing state. Reading it as a provider version gives you `1` for almost everything.

**There is no `default` and no force-replacement field.** The eight attribute keys are `computed`, `deprecated`, `description`, `description_kind`, `optional`, `required`, `sensitive`, `type`. See `docs/findings/001-...`.

**An attribute can be written as a block.** In AWS 5.82.2 `aws_security_group.ingress` is an *attribute* of type `set(object(...))`, not a `block_type` — and every example in the world writes it as `ingress { ... }`. Completion has to offer both shapes, so the index keeps the object's fields rather than flattening the type to `set`. `aws_instance.root_block_device` is the other way round: a real block type.

**A type name can be both a resource and a data source.** `aws_ami` is both. Any lookup takes the kind as an argument rather than inferring it.

**`CompletionContext.get_bounds()` returns three values**, `(found, start, end)`. Unpacking it as two raises inside a `populate_async` callback, where the only visible symptom is a `GTask ... finalized without ever returning` warning and a popup that stays empty. It was found by driving the real popup; nothing else noticed.

**A `GtkSource.CompletionProvider` written in Python hasn't been made to work here.** `do_populate_async` has to hand back a `GAsyncResult` that `do_populate_finish` can read. Building one with `Gio.Task.new(self, cancellable, callback, data)` and returning either a boxed value or a boolean both end the same way: `g_task_get_source_object: assertion 'G_IS_TASK (task)' failed`, then a segmentation fault, with the assertion firing before any Python in `populate_finish` runs.

The engine side is finished and tested (`engine/schema/completion.py`); only the popup is unwired. Whoever picks this up should try a `GtkSource.CompletionWords` subclass, or check whether this PyGObject version can construct a task the C side accepts at all, before writing more provider code.

**Headless screenshots work, and every way of getting them wrong is silent.** The cause of a blank or stale picture is almost always that the main loop wasn't iterated enough, not the capture API.

- **Wait for the condition, never for a duration.** A fixed `pump(1.2)` is a guess about somebody else's machine. Waiting until the thing being checked is actually true gives the loop as many iterations as it needs, and it is what made this work.
- A **fresh** `Gtk.WidgetPaintable` per screenshot is correct. Don't cache one: a cached paintable saves every image as a copy of the first frame, which passes every check while the pictures are worthless.
- `invalidate_contents()` doesn't rescue a stale paintable, and requesting extra frame phases doesn't rescue an empty one.
- `snapshot_child` warns *"without a current allocation"* after any widget rebuild.
- `import -window root` under `xvfb` captures a blank screen: with no window manager the window is never mapped to X.

**The trap that hid all of this**: images from earlier runs sit on disk looking correct, so the files being read aren't the files the run just wrote. `gui-smoke.py` deletes the directory before it starts, fails when a screenshot didn't save, and fails when its screenshots aren't all different from each other.

**A `GtkSource.CompletionProvider` written in Python hasn't been made to work here.** `do_populate_async` has to hand back a `GAsyncResult` that `do_populate_finish` can read. Building one with `Gio.Task.new(self, cancellable, callback, data)` and returning either a boxed value or a boolean both end the same way: `g_task_get_source_object: assertion 'G_IS_TASK (task)' failed`, then a segmentation fault, with the assertion firing before any Python in `populate_finish` runs.

The engine side is finished and tested (`engine/schema/completion.py`); only the popup is unwired. Whoever picks this up should try a `GtkSource.CompletionWords` subclass, or check whether this PyGObject version can construct a task the C side accepts at all, before writing more provider code.

**Screenshotting a GTK4 window from a headless run doesn't work reliably here, and every way of getting it wrong is silent.**

The first screenshot of a run saves and the rest usually don't. This went unnoticed for most of a session because the images from *earlier* runs were still on disk and looked correct — so the files being read weren't the files the run had just written. `gui-smoke.py` deletes the directory before it starts now, for exactly that reason.

- A **fresh** `Gtk.WidgetPaintable` per screenshot receives contents the first time and produces an empty node for every call after a widget rebuild, whatever frame phases you request. Result: the first image saves and the rest silently don't.
- A **cached** paintable saves every image and freezes on the first frame, so every screenshot is a byte-identical copy of the first. `invalidate_contents()` doesn't help.
- `snapshot_child` gives a real node until the first rebuild, then warns *"without a current allocation"* and returns nothing, because the frame clock isn't advancing under a hand-rolled main-loop pump.
- `import -window root` under `xvfb` captures a blank 290-byte screen: with no window manager the window is never mapped to X.

The behavioural checks are unaffected — they read widget state directly and are real. **Only the pictures are wrong**, and the failure is silent in every variant, which is why `gui-smoke.py` now fails when its screenshots aren't all different from each other.

**What the smoke does now:** a fresh paintable per screenshot, which is right most of the time and occasionally misses one, and two checks that turn either failure into a red run — one for a screenshot that didn't save, one for screenshots that aren't all different from each other. Of the two ways this can be wrong, take the loud one.

Whoever picks this up: try running the smoke against a real display rather than `xvfb`, or a nested compositor with a window manager, before writing more capture code.

**A `Gtk.TextTag` that adds line height doesn't change `get_line_yrange` until a layout pass has run.** Apply the tag and ask immediately and you get the old height — so anything positioned from that answer lands short by exactly the height you just added. In the verdict bands that meant every band drawn on top of the line of code it belonged to, while every check passed. Place from an idle callback, not from the function that applied the tag.

**`Adw.TabPage` is a `GObject`, not a `Gtk.Widget`.** It can't take a CSS class, so a tab can't have coloured edges, a coloured background or any per-tab styling. What it has is `icon`, `indicator-icon`, `title`, `tooltip` and `needs-attention`.

Sheet 10's anatomy — git on the left edge, plan impact along the bottom, unsaved on the right — isn't reachable through `Adw.TabBar`. Everything it wants to *say* fits in two icon slots and a title; the geometry doesn't. Buying the edges means writing a tab bar, which costs drag-to-reorder, drag-out-to-split, the overflow behaviour and `Adw.TabOverview`. That is a decision rather than a task.

**`Gtk.TextBuffer.get_selection_bounds()` returns an empty tuple when nothing is selected**, and a `(start, end)` pair when something is. There is no found flag, unlike almost every other multiple-return in this API — unpacking it as three values raises `not enough values to unpack (expected 3, got 0)` on the ordinary case of a cursor with no selection.

**`get_iter_at_offset` returns a bare `Gtk.TextIter`; `get_iter_at_line` returns `(found, iter)`.** Same buffer, same API, two conventions — and the offset one raises `cannot unpack non-iterable TextIter` if you assume otherwise. Offsets are characters, not bytes, so they line up with Python string indices.

## `get_line_at_y` returns the iterator first, the top second

```python
target_iter, line_top = view.get_line_at_y(buffer_y)
```

Unlike `get_iter_at_line`, there is no found flag — a y outside the buffer
clamps to the nearest line rather than reporting a miss. So a click below the
last line finds the last line, and the caller has to decide whether that is
what it wanted.

`window_to_buffer_coords` returns `(buffer_x, buffer_y)`, both named, and it is
needed before `get_line_at_y` whenever the y came from a gutter widget rather
than the text window.

## A gutter renderer is a `Gtk.Widget` in GtkSourceView 5

`GtkSource.GutterRenderer` has no `activate` signal in GTK4. It is a widget, so
attach a `Gtk.GestureClick` to the renderer itself and map the y through
`window_to_buffer_coords`. `set_activate_signal` exists and is a different
mechanism, for a signal you define yourself.

## `Gtk.SearchEntry` debounces `search-changed`

The signal fires about 150ms after typing stops, which is right for a search
that costs something and wrong for one over a list already in memory — and it
means a test that sets the text and reads the result immediately sees nothing.

`changed` is on `Gtk.Editable` and fires at once. `SearchEntry` still gives the
icon and the clear button.

## `GtkSource.SearchContext` counts in the background

`get_occurrences_count()` returns `-1` while the scan is running, and the scan
starts asynchronously — so reading the count straight after setting the search
text always gives `-1`. Connect to `notify::occurrences-count` and update when
it fires.

Printing "no matches" for `-1` is a lie: it means *counting*, not *none*. A test
has to run the main loop until the notify arrives, exactly as the interface does.

## `forward_to_line_end` moves to the next line when already at one

If the iterator already sits at the end of a line — which is always true of an
empty line — it moves to the end of the *following* line. Selecting "to the end
of line N" therefore silently reaches line N+1 whenever N is blank.

Guard it with `ends_line()` and only move when there is something to move past.

## `Adw.TabPage` has `get_pinned` and no setter

Pinning belongs to the view: `Adw.TabView.set_page_pinned(page, pinned)`. The
getter on the page makes it look like a property of the page, and
`page.set_pinned(...)` fails with an `AttributeError` at run time rather than
at import.
