"""The file rail, decided here so a window only has to draw it.

**The rail is files and nothing else.** A Stacks section under them cost four
rows of permanent height, which on a two-hundred-file repository pushes the
tree below the fold — and on the ordinary day it said nothing at all. Three
quiet rows train you to stop looking at that corner, and then they are still
not looked at on the day one matters. What replaced it is a verdict-line chip
that appears only when something is behind, and a glyph on the one root module
it is about.

What a large repository actually needs, in the order it needs it:

1. **Type to filter.** Worth more than everything else here combined, once the
   tree stops fitting on the screen.
2. **Root modules as the top level.** They are what a plan runs on. A `modules/`
   folder full of things nobody deploys directly is not the top of the tree.
3. **The shared part of a path, said once and quietly.** Three root modules
   under `envs/` used to be three rows beginning with `envs/` in full ink, so
   the three characters that differed were the quietest thing on each row.
4. **A folder that says it is one.** `network` and `network.tf` were one glyph
   apart, and the glyph was on the wrong side.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entry:
    """One row of the tree, before anything has decided how it looks."""

    name: str
    # Where it sits: 0 is a root module, 1 is a file inside one.
    depth: int = 0
    is_folder: bool = False
    key: str = ""

    @property
    def shown(self) -> str:
        """A folder says it is one, on the side a reader looks for it."""
        return f"{self.name}/" if self.is_folder else self.name


@dataclass
class Filtered:
    """What survives a filter, and how much did not."""

    entries: list[Entry] = field(default_factory=list)
    # Where the typed characters landed in each name, so they can be marked.
    marks: dict[str, tuple[tuple[int, int], ...]] = field(default_factory=dict)
    hidden: int = 0
    term: str = ""

    @property
    def is_filtered(self) -> bool:
        return bool(self.term)

    def summary(self) -> str:
        """What is being shown, in the units the rail is read in.

        **What is shown, not what is hidden.** "318 hidden" was accurate and
        useless: it counted every file in every collapsed module, so it was
        larger than the number of rows the reader could see it against.

        A rail is read as a list of modules with files under them, so that is
        what it counts. Absent when nothing is filtered out.
        """
        if not self.hidden:
            return ""
        modules = sum(1 for entry in self.entries if entry.is_folder)
        files = len(self.entries) - modules
        said = [f"{modules} module{'' if modules == 1 else 's'}"] if modules else []
        if files:
            said.append(f"{files} file{'' if files == 1 else 's'}")
        return " · ".join(said) or "nothing"


def quiet_prefixes(names: list[str]) -> dict[str, str]:
    """The leading path each name shares with at least one of its neighbours.

    `envs/prod`, `envs/staging` and `envs/dev` all share `envs/`, which is then
    drawn once and quietly rather than three times in full ink.

    **Per group, not across the whole list.** A real repository is not one
    family: `~/Development/terraform` has eleven roots under `examples/` and
    sixteen under `modules/`, and a single shared prefix over all twenty-seven
    is the empty string — so every row was drawn in full ink and the eight
    characters they had in common were the loudest thing in the rail. Asking
    the question per group gives `examples/` to one half and `modules/` to the
    other, and a name that is on its own keeps all of itself.

    The last segment is never eaten. A row with its own name removed says
    nothing at all.
    """
    found: dict[str, str] = {}
    for name in names:
        parts = name.split("/")
        quiet = ""
        # The longest leading run this name shares with somebody else, stopping
        # one segment short of its own end.
        for at in range(1, len(parts)):
            lead = "/".join(parts[:at]) + "/"
            if any(other != name and other.startswith(lead) for other in names):
                quiet = lead
        found[name] = quiet
    return found


def shared_prefix(names: list[str]) -> str:
    """What every one of these names begins with, or nothing.

    Kept for the case where a caller genuinely wants one answer for one group;
    `quiet_prefixes` is what the rail uses, because the rail is never one group.
    """
    if len(names) < 2:
        return ""
    quiet = quiet_prefixes(names)
    first = quiet[names[0]]
    return first if all(quiet[name] == first for name in names) and first else ""


def marked(name: str, term: str) -> tuple[tuple[int, int], ...] | None:
    """Where each character of the term landed, or nothing when it did not match.

    Contiguous runs are returned as one span, so a name matched on a whole word
    is marked as a word rather than as a row of separate letters.
    """
    if not term:
        return ()
    haystack, needle = name.lower(), term.lower()
    at = 0
    hits: list[int] = []
    for character in needle:
        found = haystack.find(character, at)
        if found < 0:
            return None
        hits.append(found)
        at = found + 1
    spans: list[tuple[int, int]] = []
    for hit in hits:
        if spans and spans[-1][1] == hit:
            spans[-1] = (spans[-1][0], hit + 1)
        else:
            spans.append((hit, hit + 1))
    return tuple(spans)


def filtered(entries: list[Entry], term: str) -> Filtered:
    """The tree as it is with a filter typed into it.

    **A match keeps its ancestors.** A file shown without the module it is in is
    a search result, not a tree, and the whole reason to filter in place rather
    than jump to the first hit is that the shape survives.
    """
    if not term.strip():
        return Filtered(entries=list(entries), marks={}, hidden=0, term="")

    said = term.strip()
    marks: dict[str, tuple[tuple[int, int], ...]] = {}
    hit: list[bool] = []
    for entry in entries:
        found = marked(entry.name, said)
        hit.append(found is not None)
        if found is not None:
            marks[entry.key or entry.name] = found

    keep = [False] * len(entries)
    for at, entry in enumerate(entries):
        if not hit[at]:
            continue
        keep[at] = True
        # Its ancestors, which are the nearest rows above it at each lower depth.
        depth = entry.depth
        for back in range(at - 1, -1, -1):
            if depth == 0:
                break
            if entries[back].depth < depth:
                keep[back] = True
                depth = entries[back].depth
    # A module that matched brings its files with it: the module is what you
    # were looking for, and an empty one tells you nothing about what is in it.
    for at, entry in enumerate(entries):
        if not (keep[at] and hit[at] and entry.is_folder):
            continue
        for forward in range(at + 1, len(entries)):
            if entries[forward].depth <= entry.depth:
                break
            keep[forward] = True

    kept = [entry for at, entry in enumerate(entries) if keep[at]]
    return Filtered(entries=kept, marks=marks, hidden=len(entries) - len(kept), term=said)
