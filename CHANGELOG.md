# Changelog

What changed, for somebody deciding whether to update. The investigations
behind the harder changes are in `docs/findings/`.

This project has not been released. Everything below is under `Unreleased`, and
the first version number will be cut when the editor is usable for a day's work
without surprises.

## Unreleased

### Documentation

- **The rules for contributing are in `CONTRIBUTING.md`**: fixtures come from the
  real tool, and it says which architecture rules a test enforces and which are
  held by review.
- **The privacy test also refuses per-user temporary paths**: a scratch
  directory named for a login and a user id names the account that captured a
  fixture.

### Changed — the design, finished

- **One click in the rail previews a file; two open it.** A preview shows the
  file in front of you and the next one replaces it. One click opens for good
  only where *Open a file from the rail with* says a single click — which is no
  longer the default. *Keep a previewed file open* now only decides whether
  typing in a preview keeps it, since a double click always does; a setting
  that still says *never* behaves, and shows, as *a double click*.
- **The Plan button turns red when the plan destroys or replaces something**,
  and leaves the header when there is no workspace or no engine to plan with.
  It looked the same whether a plan created two things or destroyed forty.
- **An apply can be stopped from the screen watching it.** *Stop after this
  resource* lets the one in flight finish and starts nothing further, which is
  how the engine shuts down without leaving state that describes
  infrastructure that already moved.
- **Each resource in an apply shows how long it took**, and each outcome takes
  its own colour — a destroy that succeeded is no longer drawn like a create.
- **Code rows are 16px where they were 23**, which puts about 40% more code on
  screen. GTK multiplies `line-height` by the font's own line box rather than
  its size, so the stylesheet's 1.45 produced a row far taller than intended;
  the row is now set in pixels from the font in use. See `docs/findings/019`.
- **`!` in the palette lists what is stopping the plan** and jumps to its line.
- **Escape closes whatever is on top**, the command palette included, and gives
  the keyboard back to where it was.
- **Every click does what the keyboard does**: a planned change opens its line,
  a gutter mark explains its finding and has a menu, and the palette offers
  every command rather than only the ones with a key.
- **The drawer opens at 38% of the window**, stops growing on its own at 45%,
  and can be dragged to 70%.
- **The rail is a file tree**: one level to start, and folders open when you
  open them.
- The drawer tab and the status chip both say **Exposure**; the failed-plan
  disclosure says *Show the original*; consequence groups are a rule down the
  left edge rather than a box.

### Added — tested against a real emulator

- **`make integration`** runs every engine command the application issues —
  nine of them, found by reading the code rather than listed by hand — against
  a disposable MiniStack, and checks the infrastructure through its own API
  rather than trusting the engine's output. No cloud credentials involved.
- It found that **a filtered `test` run executed nothing and reported a pass**:
  the filter was an absolute path, which the engine matches against nothing.

### Changed — the interface, redesigned

- **The editor shows about a quarter more code.** Line height came down from
  1.85 to 1.45, and annotations moved out of rows of their own into a lane at
  the right of the line they are about — so **line *n* is at *n* times the row
  height, always**. The numbers are a ruler you can count on again, paging
  moves a predictable distance, and the change map beside the buffer maps onto
  what is in front of you.
- **One permanent explanation per screenful, and it is the worst one.**
  Everything else stays a gutter mark until you go to the line.
- **A spine**: one continuous bar down each block the plan touches, instead of
  the same glyph repeated on every line of it. An exposure gets a mark and no
  spine, because the spine says *the plan will do something here* and an
  exposure is a property of what the block already is.
- **Seven gutter marks that differ by shape as well as colour**, so the gutter
  survives a monochrome screenshot and a red-green reader.
- **The verdict line**: twenty-four pixels, three zones, and it never leaves.
  What applying would do, then cost, exposure, convergence and tests as chips
  that each open the tab explaining them, then the file facts. **A chip with
  nothing to say is absent, not empty**, and as the window narrows chips fall
  off the right, cheapest first — the verdict never drops. It turns for exactly
  one condition: a plan that will not run.
- **A stale plan says it is stale**, and marks its counts as of when, rather
  than showing them as current.
- **The right-hand inspector is gone.** It answered the same five questions the
  drawer answers, in a permanent 320-pixel column too narrow for any of them.
  The 320 pixels went to the buffer.
- **One header row**, four controls and a title. The menu bar is off by
  default; its eight menus live in the primary menu and move to the bar when it
  is turned on, so no item is ever in two places. **Terraform hangs off the run
  control's caret**, which is one click from a button that is always visible.
  Chrome above the first line of code went from 92 pixels to 64.
- **The rail is a file tree, one level at a time.** It shows the repository's
  immediate children — directories then files, alphabetical, dotfiles kept —
  and reads nothing below them until a directory is expanded. Expanding one
  reveals its children and leaves *those* closed; opening a file expands its
  own ancestors and no other directory; and what you have opened survives a
  plan finishing.

  It was a flat list of every module in the workspace with the path flattened
  into the row — `examples/account-baseline/` and `modules/context/` as peers,
  each with its files under it. On a repository with 63 modules that is 273
  rows with no hierarchy in them, and a file outside a Terraform module did not
  appear at all.

  Git state is two pixels on the left edge, the plan's count is on the right,
  and **a directory carries the sum of what is under it**. Typing in the rail
  opens the way to what matches. Stacks are not in it: a resident section that
  says nothing on the ordinary day trains you to stop looking at that corner,
  so it is a verdict-line chip that appears only when a stack is behind
  something it depends on.
- **Eleven syntax colours instead of six.** `resource`, the provider's
  `aws_instance` and your own `api` are three different kinds of thing and are
  now three colours; the block keyword had none at all. The two labels are
  told apart by reading the syntax tree, because GtkSourceView's grammar
  captures both quoted words as one span and no colour scheme can separate
  them.
- **A Cost tab**, so the estimate is a panel rather than text dumped into the
  output tab.
- **Preferences is five pages instead of eight**, and a text setting says *Not
  set* rather than sitting blank. **The font row says when the family it names
  is not installed**, because a font that silently substitutes is a design that
  silently does not exist.
- **Selecting a word outlines every other occurrence**, and the caret line
  takes a wash so you can find it after looking away.
- **`Ctrl+D` answers.** It selects the next occurrence and says once what
  multiple cursors would have done and why they are not there — with
  **Help → What Backsight will not do**, which lists every toolkit limit, every
  deliberate refusal and everything not built yet.
- Navigation history: **Back and Forward**, which did not exist anywhere.

### Fixed

- **A quick double click in the rail is a double click.** It was read as one
  click, so only two clicks a second apart counted.

- **Refusing to open a file no longer closes the file you were reading.** The
  previous tab was closed before the new one was read, so a file that is not
  UTF-8 — which is correctly refused — took a readable file with it.
- **Two menu items no longer run one command.** *Line wrap* and *Word wrap*,
  *Ruler* and *Rulers*, and worst of all *Whitespace* and *Show whitespace*,
  which ran through different code and could disagree about what the buffer was
  doing. The guard compared labels; it compares actions now.
- **The last drawer tab is no longer cut off.** *Esc to close* was sitting in
  the tab row, taking exactly the width the last tab needed.
- **The irreversible group no longer fills its card.** Blocked is the only
  element allowed a full coloured background — that is the whole difference
  between *this is dangerous* and *this will not run*.
- The new-tab `+` moved out from beside the filename, and the plan's mark on a
  tab is no longer the desktop's *add* icon, which read as a second new-tab
  button.
- Console errors wrap at a word rather than mid-sentence, and the prompt is
  pinned under the transcript rather than floating in the middle of the drawer.
- **A warning about local state is no longer on every row and across the top of
  the window.** It was a 110-pixel banner above the window controls and a glyph
  on each of 27 module rows, in a repository where nothing has a backend — so
  it distinguished nothing and was dismissed on reflex. It is a `local state`
  fact in the verdict line, and a clause in the apply footer, which is the last
  thing read before the button it is actually about.
- The provider list no longer prints the same provider twice. It asks the
  module the open file is in rather than every root module in the repository.

### Added

- **A library of reusable Terraform** — snippets, examples, recipes and
  runbooks in one place. `Ctrl+E` to find one, Return to put it in the file
  with the first field selected, `Ctrl+Shift+E` to keep the block in front of
  you. Twelve entries ship, plus one generated per resource type from the
  provider schema, plus anything a team shares or a workspace commits.
- **A module catalog.** A folder of modules, each read for its own variables
  and outputs, appearing in the library ready to call.
- **Provider documentation**, mirrored from each provider's own repository,
  version-matched to the lock file, with its examples insertable.
- **Policy findings** from whichever scanner is on PATH, at the line that
  caused them. Nothing is enforced.
- **What a change costs**, with usage-priced resources marked as not estimable
  rather than reported as zero. No prices ship.
- **Credentials**, discovered without ever holding one, and a different profile
  for reading than for applying where somebody has both.
- **Git**: staging per file, commit, push behind a question, branches, clone.
- **A rehearsal against the local emulator**, which had been written and never
  called.
- **Extract to a module**, with the `moved` blocks that stop it being a destroy.
- **Peek** at a hidden panel without changing the layout.
- **A history** of every plan, apply and drift check, and what each apply
  printed.

- **Apply.** The plan you reviewed, applied and shown happening — the same
  resources in the order you read them, each moving as the engine reaches it.
  Three endings rather than two: applied, stopped part way, and nothing changed.
- **Verification after apply.** The state is read back and checked against what
  the plan intended. It says which of the two it checked — recorded in state,
  not serving traffic — and says it could not check rather than reporting
  success when there is no local state to read.
- **Drift.** What changed outside Terraform, from a refresh-only plan. Names the
  resource and the attributes that moved, with the value each was and is, and
  opens where the resource is declared. Can run on a timer; off by default.
- **Newer provider versions.** Whether a locked provider is behind. The only
  thing here that reaches the network, and off unless you turn it on.
- **The left rail folds.** Each of its four parts collapses under its own
  heading and can be removed from the View menu, remembered per workspace.
- **An Output tab**, carrying whatever the engine last printed, verbatim.
- **A prompt before closing a tab with unsaved changes.**

### Changed

- **Every setting in Preferences now does something.** Twenty-one of
  thirty-eight were read by nothing at all.
- **Preferences reads as words** rather than as the tokens the settings are
  stored under.
- **Text scaling is followed.** Every size was a pixel count, and a px font size
  is deaf to the desktop's scaling factor.
- **Ten shortcuts** that every editor has, including `Ctrl+O` — which the
  workspace switcher was already printing on screen — and `F11`.
- **Apply needs credentials only when the plan reaches outside this machine**,
  read from the plan rather than assumed.
- The container sandbox is called **Rehearsal**. It was called "Drift check",
  which is a different feature.

### Fixed

- **Cancelling a plan stops it.** It discarded the answer and left the engine
  running, holding the state lock.
- **The rail can be hidden.** Collapsed drew exactly what shown drew, so the
  toggle flipped between two identical states.
- **Run plan runs a plan.** It saved and relied on the save to start one.
- **Nothing empty holds the bottom of the window open** after Escape.
- **No notice outlives what it is about.** Five were toasts asked to last
  forever.
- Reading and writing the settings file disagreed about `XDG_CONFIG_HOME`.
- The wheel could not build.

### Still missing

- **Signing in through IAM Identity Center**, which needs a real one to capture
  anything against.
- **State locking is not surfaced** — a lock could not be held on this machine
  to capture what one says.
- **OPA and Trivy**, neither installed here.
- **Import block generation**: the id format is per resource type and the
  provider schema does not carry it.

### Known gaps

- **The tab strip is 41px, not the 28 the design asks for.** The toolkit's tab
  measures its own minimum and no stylesheet can move it; the rest costs
  drag-to-reorder, drag-out-to-split and the tab overview. See
  `docs/findings/017` and `docs/design-conformance.md`.
- **Multiple cursors, column selection and code folding are not built**, and
  will not be. GtkSourceView 5 has no API for any of them, and building them
  means reimplementing every editing path — which risks round-trip safety and
  the byte-exact guarantee. Decided rather than pending; see
  `docs/findings/002`.
- **Apply against a real provider is unproven here.** It is exercised end to end
  against resources that reach nothing outside the machine, because this
  installation has no credentials and touches no cloud account.
- **Apply against a real provider needs credentials this installation does not
  have**, so nobody has run it against an account.
