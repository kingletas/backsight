"""The verdict line: the one strip that never leaves, in three zones.

It is the product's answer to its own question. **What would applying this do?**
— answered without opening a panel, at every width, in every preset.

```
＋2 ◆1 ▲1 ▼1   $124/mo ↑   1 exposure   86% converged   4/5 tests    Ln 10, Col 34   Spaces: 2   HCL
└── verdict ──┘└──────────── consequences, each a chip ───────────┘  └───────── file facts ────────┘
```

Four rules make it work, and each of them is a rule about what it does *not*
say:

- **A chip with nothing to say is absent, not empty.** No prices means no cost
  chip — not a chip announcing that prices are not configured. A signal that
  fires when nothing is wrong trains people to stop reading the channel, and
  it takes the real one down with it.
- **The verdict never drops.** As the window narrows, chips fall off the right,
  cheapest first. What applying would do stays at every width.
- **The strip is the only element allowed to change its own background**, and it
  does it for one condition: a plan that will not run.
- **A stale plan says it is stale.** Counts from before an edit, presented as
  current, are the confident-but-wrong claim this whole product exists against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Tone(Enum):
    """What a segment is, which decides how it is drawn.

    `BLOCKING` is the only one that was ever coloured in the line this replaces,
    and the reason still holds: five negatives in a row become facts, and only
    the thing stopping the next action earns a colour. The four consequence
    tones are for the counts, which carry a colour each because that is the
    whole point of counting them separately.
    """

    FACT = "fact"
    BLOCKING = "blocking"
    SAFE = "safe"
    DISRUPTIVE = "disruptive"
    IRREVERSIBLE = "irreversible"
    ACCENT = "accent"


# What each plan action is called, its glyph, and what it costs you. The glyph
# is not decoration: a bare number reads as a total, and these four are not
# totals of the same thing.
ACTIONS = (
    ("create", "＋", Tone.SAFE),
    ("update", "◆", Tone.DISRUPTIVE),
    ("replace", "▲", Tone.IRREVERSIBLE),
    ("delete", "▼", Tone.IRREVERSIBLE),
)

# Which chip falls off first when the window narrows. Lower goes first, and the
# order is what each one costs you to lose: tests and convergence are checks you
# ran and can run again, cost is a number you can open, exposure is a security
# fact, and the stacks chip only exists when something is already wrong.
WEIGHT = {
    "tests": 1,
    "convergence": 2,
    "unformatted": 3,
    "cost": 4,
    "exposure": 5,
    "drift": 6,
    "stacks": 7,
}


@dataclass(frozen=True)
class Segment:
    """One thing the line says."""

    text: str
    tone: Tone = Tone.FACT
    action: str | None = None
    tooltip: str = ""
    # Drop order within the chip zone. Nought never drops.
    weight: int = 0

    @property
    def is_clickable(self) -> bool:
        """Every chip opens the drawer tab that explains it. A number that goes
        nowhere is not a finding."""
        return self.action is not None


@dataclass
class VerdictLine:
    """What the strip holds, in the three zones it is read in."""

    verdict: list[Segment] = field(default_factory=list)
    chips: list[Segment] = field(default_factory=list)
    facts: list[Segment] = field(default_factory=list)
    # The one condition worth taking a whole strip of the window for.
    will_not_run: bool = False

    @property
    def summary(self) -> list[Segment]:
        """The left of the line, for anything that reads it as two halves."""
        return self.verdict + self.chips

    @property
    def position(self) -> list[Segment]:
        return self.facts

    def texts(self) -> list[str]:
        return [segment.text for segment in self.verdict + self.chips + self.facts]

    def within(self, chips: int) -> VerdictLine:
        """The line as it fits when there is only room for so many chips.

        Cheapest first, and the verdict is never one of them.
        """
        kept = sorted(self.chips, key=lambda chip: -chip.weight)[: max(0, chips)]
        order = {id(chip): at for at, chip in enumerate(self.chips)}
        return VerdictLine(
            verdict=list(self.verdict),
            chips=sorted(kept, key=lambda chip: order[id(chip)]),
            facts=list(self.facts),
            will_not_run=self.will_not_run,
        )


def plan_summary(counts: dict[str, int]) -> str:
    """`＋2 ◆1 ▲1`, the whole plan in one glance.

    Every count carries a glyph and no count is shown as a zero, because an
    action with nothing to do is not a fact about this plan.
    """
    return " ".join(f"{glyph}{counts[name]}" for name, glyph, _tone in ACTIONS if counts.get(name))


def counted(counts: dict[str, int]) -> list[Segment]:
    """One segment per action, each with its own glyph and its own colour."""
    return [
        Segment(
            text=f"{glyph}{counts[name]}",
            tone=tone,
            action="plan",
            tooltip="What applying would do",
        )
        for name, glyph, tone in ACTIONS
        if counts.get(name)
    ]


def build(  # noqa: PLR0912, PLR0913
    *,
    counts: dict[str, int] | None = None,
    exposures: int | None = None,
    coverage: int | None = None,
    tests: tuple[int, int] | None = None,
    drifted: int | None = None,
    cost: str = "",
    cost_direction: str = "",
    stale_stacks: int | None = None,
    waiting_stacks: int = 0,
    unformatted: bool = False,
    line: int | None = None,
    column: int | None = None,
    indentation: str = "",
    language: str = "",
    provider: str = "",
    branch: str = "",
    state: str = "",
    blocked: str = "",
    problems: int = 0,
    planned: bool = False,
    planning: str = "",
    stale_edits: int = 0,
    applying: tuple[int, int] | None = None,
    stopped: tuple[int, int] | None = None,
) -> VerdictLine:
    """The line as it is right now.

    Anything unknown is left out rather than shown as a zero or a dash. An
    absence that looks like a measurement is the failure this product is built
    to avoid, and a status line is where it would be least noticed.
    """
    counts = counts or {}
    verdict: list[Segment] = []
    chips: list[Segment] = []
    will_not_run = False

    if applying is not None:
        done, total = applying
        verdict.append(
            Segment(text=f"Applying · {done} of {total}", tone=Tone.ACCENT, action="plan")
        )
    elif stopped is not None:
        done, untouched = stopped
        verdict.append(
            Segment(
                text=f"Stopped · {done} applied, {untouched} untouched",
                tone=Tone.IRREVERSIBLE,
                action="plan",
            )
        )
    elif blocked:
        # The strip turns, and nothing measured before the error is repeated
        # beside it. Last run's cost next to a live failure is a number
        # presented as current that is not.
        will_not_run = True
        said = f"Will not run — {problems} problem{'' if problems == 1 else 's'}"
        verdict.append(
            Segment(
                text=f"■ {said}" if problems else f"■ {blocked}",
                tone=Tone.BLOCKING,
                action="problems",
                tooltip=blocked,
            )
        )
        return VerdictLine(
            verdict=verdict,
            chips=[],
            facts=_facts(line, column, indentation, language, provider, branch),
            will_not_run=True,
        )
    elif planning:
        verdict.append(Segment(text=f"Planning {planning}…", tone=Tone.ACCENT))
    elif not planned:
        verdict.append(Segment(text="No plan yet", tone=Tone.FACT, action="plan"))
        verdict.append(Segment(text="Ctrl+Return to run one", tone=Tone.FACT))
    elif any(counts.values()):
        verdict += counted(counts)
        if stale_edits:
            verdict.append(
                Segment(
                    text=f"as of {stale_edits} edit{'' if stale_edits == 1 else 's'} ago",
                    tone=Tone.DISRUPTIVE,
                    action="plan",
                    tooltip="The file has changed since this plan ran",
                )
            )
    else:
        verdict.append(Segment(text="No changes", tone=Tone.FACT, action="plan"))
        verdict.append(Segment(text="Infrastructure matches the configuration", tone=Tone.FACT))

    if cost:
        chips.append(
            Segment(
                text=f"{cost} {cost_direction}".strip(),
                tone=Tone.FACT,
                action="cost",
                tooltip="What this plan changes about the monthly bill",
                weight=WEIGHT["cost"],
            )
        )
    if exposures:
        chips.append(
            Segment(
                text=f"{exposures} exposure{'' if exposures == 1 else 's'}",
                tone=Tone.IRREVERSIBLE,
                action="exposure",
                tooltip="Open the exposure findings",
                weight=WEIGHT["exposure"],
            )
        )
    if coverage is not None:
        chips.append(
            Segment(
                text=f"{coverage}% converged",
                action="convergence",
                weight=WEIGHT["convergence"],
            )
        )
    if tests is not None:
        passed, total = tests
        chips.append(
            Segment(
                text=f"{passed}/{total} tests",
                tone=Tone.FACT if passed == total else Tone.DISRUPTIVE,
                action="tests",
                weight=WEIGHT["tests"],
            )
        )
    if drifted:
        # It is true about the infrastructure whether or not this window is
        # open, which is why it is here rather than only in a panel — and it
        # opens the detail, because a number that goes nowhere is not a finding.
        chips.append(
            Segment(
                text=f"{drifted} drifted",
                tone=Tone.DISRUPTIVE,
                action="drift",
                tooltip="What changed outside Terraform",
                weight=WEIGHT["drift"],
            )
        )
    if stale_stacks:
        # The whole of what a Stacks section in the rail was for, and it appears
        # only on the day it means something. Three quiet rows every other day
        # trains you not to look at that corner at all.
        waiting = f" · {waiting_stacks} waiting" if waiting_stacks else ""
        chips.append(
            Segment(
                text=f"data is stale{waiting}",
                tone=Tone.DISRUPTIVE,
                action="stacks",
                tooltip="An upstream stack has changed since this one was planned",
                weight=WEIGHT["stacks"],
            )
        )
    if unformatted:
        chips.append(
            Segment(
                text="unformatted",
                action="format",
                tooltip="This file differs from terraform fmt — Ctrl+Shift+I",
                weight=WEIGHT["unformatted"],
            )
        )

    return VerdictLine(
        verdict=verdict,
        chips=chips,
        facts=_facts(line, column, indentation, language, provider, branch, state),
        will_not_run=will_not_run,
    )


def _facts(
    line: int | None,
    column: int | None,
    indentation: str,
    language: str,
    provider: str,
    branch: str,
    state: str = "",
) -> list[Segment]:
    """The right of the line: what is true about the file in front of you.

    The branch is here and nowhere else. It is a fact, not an action, and it was
    in the header as well — one question answered in two places, which is the
    duplication this design deletes wherever it finds it.

    So is `state`. **Local state was a banner across the top of the window**,
    110 pixels above the window controls, saying something true on open, true
    all day, and true of every module in a repository that is a library rather
    than a deployment. It stops nothing, so it is a standing fact at the size a
    standing fact deserves — and it still opens the same explanation.
    """
    facts: list[Segment] = []
    if line is not None:
        where = f"Ln {line}"
        if column is not None:
            where += f", Col {column}"
        facts.append(Segment(text=where))
    for text in (indentation, language, provider):
        if text:
            facts.append(Segment(text=text))
    if state:
        facts.append(
            Segment(
                text=state,
                action="backend",
                tooltip="Where this workspace keeps its state, and what that costs",
            )
        )
    if branch:
        facts.append(
            Segment(text=f"⑂ {branch}", action="git", tooltip="Changes, staging and commit")
        )
    return facts
