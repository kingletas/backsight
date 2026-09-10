"""Running tests, against one of three things, and never the dangerous one by default.

The table. The middle row is the one that does not exist anywhere else:

| Target      | Proves                                    | Costs                      |
|-------------|-------------------------------------------|----------------------------|
| Mocks       | config logic, expressions, expansion      | seconds, no container      |
| Sandbox     | a real apply converges                    | a local container, no money|
| Real        | everything, including account behaviour   | real money, real destruction|

FR-TST-06: **a test that would touch real infrastructure needs the same
confirmation as any apply.** `command = apply` without mocks creates and
destroys real resources, and without this one keystroke bills somebody for a
database. So `real` is refused unless it is explicitly confirmed, in code, at
the call — not by a setting somebody turned on once.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from backsight.engine.runner import process
from backsight.engine.tests.results import Results, parse

TIMEOUT = 900.0


class Target(Enum):
    """What the tests run against."""

    MOCKS = "mocks"
    SANDBOX = "sandbox"
    REAL = "real"

    @property
    def costs_money(self) -> bool:
        return self is Target.REAL

    @property
    def needs_confirmation(self) -> bool:
        """Only one of them, and it is never the default."""
        return self is Target.REAL

    @property
    def description(self) -> str:
        return {
            "mocks": "Config logic, expressions and expansion. Seconds, no container.",
            "sandbox": "A real apply against the emulator. No money, no cleanup.",
            "real": "Everything, including account behaviour. Real money, real destruction.",
        }[self.value]


DEFAULT_TARGET = Target.MOCKS


class NotConfirmed(Exception):
    """A run against real infrastructure that nobody agreed to."""

    def __init__(self) -> None:
        super().__init__(
            "Running tests against real infrastructure creates and destroys real "
            "resources. Confirm it the way an apply is confirmed, or choose the "
            "emulator instead."
        )


@dataclass(frozen=True)
class Outcome:
    """What a test run produced, including when it produced nothing."""

    results: Results
    output: str
    target: Target
    ok: bool

    @property
    def summary(self) -> str:
        return self.results.summary()


def discover(workspace: Path) -> list[Path]:
    """Every `*.tftest.hcl` under a workspace, in the order a tree shows them."""
    root = Path(workspace)
    found = [
        path
        for path in root.rglob("*.tftest.hcl")
        if ".terraform" not in path.relative_to(root).parts
    ]
    return sorted(found)


def _relative_to(workspace: Path, path: Path) -> str:
    """A filter the engine can match, which means relative to where it runs.

    An absolute path matches no test file and the engine reports a pass with
    nothing run, so a whole suite can go green having executed none of it.
    """
    try:
        return str(Path(path).relative_to(Path(workspace)))
    except ValueError:
        return str(path)


def run(
    workspace: Path,
    *,
    target: Target = DEFAULT_TARGET,
    files: list[Path] | None = None,
    confirmed: bool = False,
    environment: dict[str, str] | None = None,
    on_line: Callable[[str], None] | None = None,
    engine: str = "tofu",
) -> Outcome:
    """Runs the tests and reads what the engine said.

    `confirmed` is a parameter rather than a setting, so touching real
    infrastructure is a decision taken at the moment it happens.
    """
    if target.needs_confirmation and not confirmed:
        raise NotConfirmed

    command = [engine, "test", "-json", "-no-color"]
    for path in files or []:
        command += ["-filter", _relative_to(workspace, path)]

    result = process.start(
        command,
        cwd=workspace,
        timeout=TIMEOUT,
        environment=environment,
        on_line=on_line,
    ).wait(TIMEOUT + 30)

    return Outcome(
        results=parse(result.output),
        output=result.output,
        target=target,
        # A failing test is a successful run. Only the command failing to run
        # at all is a failure of the run itself.
        ok=result.state.value in ("succeeded", "failed"),
    )
