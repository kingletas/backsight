"""Moving resources into a module without destroying them.

FR-REF-02. Terraform matches state on the address, and a resource that moves
into a module gets a new one — `module.network.terraform_data.vpc` where it was
`terraform_data.vpc`. Without a `moved` block for each, the plan is a destroy
and a create, which for anything holding data is the worst outcome in the tool.

So the `moved` blocks are the point, and everything else is bookkeeping: cut the
blocks out of where they are, write them into the module, call it, and declare
every address that changed.

Nothing here decides whether it is safe. The gate does that by planning it and
refusing anything destructive — FR-REF-03 — which is the only way to know.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backsight.engine.hcl.navigation import blocks
from backsight.engine.refactor.edits import Edit

# What the module's own file is called. `main.tf` because that is where
# somebody opening a module looks first.
MAIN = "main.tf"


@dataclass(frozen=True)
class Extraction:
    """What moving a set of resources into a module would come to."""

    module: str
    addresses: tuple[str, ...]
    edits: tuple[Edit, ...] = ()
    appended: dict[Path, str] | None = None

    @property
    def description(self) -> str:
        count = len(self.addresses)
        return f'Extract {count} resource{"" if count == 1 else "s"} into module "{self.module}"'


def moved_blocks(module: str, addresses: tuple[str, ...]) -> str:
    """One per address, which is what stops this being a destroy and a create."""
    return (
        "\n".join(
            f"moved {{\n  from = {address}\n  to   = module.{module}.{address}\n}}"
            for address in addresses
        )
        + "\n"
    )


def module_call(module: str, source: str = "") -> str:
    """The call that replaces what was cut out."""
    where = source or f"./{module}"
    return f'module "{module}" {{\n  source = "{where}"\n}}\n'


def _span_of(text: str, block) -> tuple[int, int]:
    """The character offsets one block occupies, from the parser's own lines."""
    lines = text.splitlines(keepends=True)
    start = sum(len(line) for line in lines[: max(0, block.first - 1)])
    end = sum(len(line) for line in lines[: block.last])
    return start, end


def extract(
    path: Path,
    text: str,
    addresses: tuple[str, ...],
    *,
    module: str,
    relative_to: Path | None = None,
    source: str = "",
) -> Extraction | None:
    """What it would take to move these resources out of this file.

    Returns nothing when an address is not in the file. Moving a resource that
    is somewhere else would cut a hole in one file and write the wrong thing
    into the module.
    """
    wanted = tuple(dict.fromkeys(addresses))
    if not wanted or not module.strip():
        return None

    found = {}
    for block in blocks(text.encode("utf-8")):
        if block.address in wanted:
            found[block.address] = block
    if set(found) != set(wanted):
        return None

    here = Path(path) if relative_to is None else Path(path).relative_to(relative_to)
    moved: list[str] = []
    edits: list[Edit] = []
    for address in wanted:
        block = found[address]
        start, end = _span_of(text, block)
        moved.append(text[start:end].rstrip("\n") + "\n")
        edits.append(
            Edit(
                path=here,
                start=start,
                end=end,
                replacement="",
                reason=f"moved into module {module}",
            )
        )

    into = Path(module) / MAIN
    appended = {
        into: "\n\n".join(said.rstrip("\n") for said in moved) + "\n",
        here: "\n" + module_call(module, source) + "\n" + moved_blocks(module, wanted),
    }
    return Extraction(
        module=module.strip(),
        addresses=wanted,
        edits=tuple(edits),
        appended=appended,
    )


def proposal_for(extraction: Extraction):
    """The extraction as something the gate can verify and apply."""
    from backsight.engine.refactor.gate import Proposal

    return Proposal(
        description=extraction.description,
        edits=list(extraction.edits),
        appended=dict(extraction.appended or {}),
    )


def is_a_name(said: str) -> bool:
    """Whether this could be a module directory and a Terraform identifier."""
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", said.strip()))
