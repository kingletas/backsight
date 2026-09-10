"""Your house rules, filled into a snippet before you see it.

FR-SCH-18. A generated snippet arrives correct and generic: `name`, `""`, an
empty tag map. Somebody then types the same team prefix and the same four tags
into it, every time, which is the thing this whole feature exists to stop one
level up.

So a snippet's placeholders can carry what a team already decided. Two rules,
both read from settings and neither invented here:

**A naming pattern**, with `{name}` and `{environment}` in it, so the first
placeholder arrives as `acme-prod-` rather than as `name`. The braces are ours
and are filled in here — **an HCL interpolation cannot go in a pattern**,
because a placeholder default ends at its first `}` and `${var.environment}`
inside one would be cut in half. A pattern carrying one is refused rather than
silently mangled.

**Tags every resource carries**, filled into a `tags` block if the snippet has
one and left alone if it does not — adding a `tags` argument to a resource type
that has no such attribute produces a file that will not plan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# The `tags = { ... }` a generated snippet writes, so the filled version can
# replace exactly that and nothing that looks like it.
EMPTY_TAGS = re.compile(r"(?P<indent>[ \t]*)tags(?P<pad>\s*)=\s*\{\s*\$\{(?P<stop>\d+)\}\s*\}")

# The first placeholder, which is a resource's name by construction.
FIRST_NAME = re.compile(r'"\$\{1:(?P<default>[^}]*)\}"')


@dataclass(frozen=True)
class House:
    """What a team already decided, as far as a snippet is concerned."""

    naming: str = ""
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def any(self) -> bool:
        return bool(self.usable_naming or self.tags)

    @property
    def usable_naming(self) -> str:
        """The pattern, or nothing when it carries what it cannot carry.

        A placeholder default ends at its first `}`, so an interpolation inside
        one is cut in half. Refused rather than mangled.
        """
        said = self.naming.strip()
        return "" if "${" in said else said

    def name_for(self, *, name: str = "name", environment: str = "") -> str:
        """The pattern with our own braces filled in."""
        pattern = self.usable_naming
        if not pattern:
            return name
        return (
            pattern.replace("{name}", name)
            .replace("{environment}", environment or "environment")
            .strip()
        )


def from_settings(settings) -> House:
    """The two conventions, out of the settings file.

    Tags are `key=value` pairs separated by commas, because that is what
    somebody types once and never edits again — a nested structure in a
    settings file for two tags is a form nobody fills in.
    """
    said = str(settings.get("conventions.tags", "") or "")
    tags = {}
    for pair in said.split(","):
        key, _, value = pair.partition("=")
        if key.strip() and value.strip():
            tags[key.strip()] = value.strip()
    return House(naming=str(settings.get("conventions.naming", "") or "").strip(), tags=tags)


def apply(body: str, house: House, *, environment: str = "") -> str:
    """A snippet with the house rules filled in.

    Nothing is added that was not already there. A `tags` block is filled only
    when the snippet has one, because adding the argument to a resource type
    that has no such attribute produces a file that will not plan.
    """
    if not house.any:
        return body
    said = body
    if house.usable_naming:

        def named(match: re.Match) -> str:
            filled = house.name_for(name=match.group("default"), environment=environment)
            return f'"${{1:{filled}}}"'

        said = FIRST_NAME.sub(named, said, count=1)
    if house.tags:
        said = EMPTY_TAGS.sub(lambda m: _tags(m, house.tags), said)
    return said


def _tags(match: re.Match, tags: dict[str, str]) -> str:
    """The tag block, written the way `tofu fmt` would leave it."""
    indent = match.group("indent")
    inner = indent + "  "
    width = max(len(key) for key in tags)
    lines = [f'{inner}{key.ljust(width)} = "{value}"' for key, value in tags.items()]
    stop = match.group("stop")
    lines.append(f"{inner}${{{stop}}}")
    return f"{indent}tags{match.group('pad')}= {{\n" + "\n".join(lines) + f"\n{indent}}}"
