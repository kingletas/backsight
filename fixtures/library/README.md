# A workspace shaped like a real module library

**Everything in it is invented.** It exists because this project's other
fixtures are four to ten files in one or two modules, and every rule the rail
broke on a real repository is a rule about **twenty-something of something**.

What it has that a small fixture does not:

- **Two groups of root modules** — `examples/` and `modules/` — which share no
  common prefix between them, so a single shared prefix over all of them is the
  empty string.
- **Root modules under `modules/` beside library modules under `modules/`**, so
  the two have to be told apart by something other than where they live.
- **No backend anywhere**, so a warning about local state is true of every row
  and distinguishes none of them.
- **Enough files that expanding every module fills the rail** before the top of
  the tree has been read.

Nothing here plans: there is no provider to plan against and no credentials to
plan with. It is a workspace to *look* at.
