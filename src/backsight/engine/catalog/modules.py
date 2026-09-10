"""Reading a module well enough to call it correctly.

A module's public interface is its `variable` and `output` blocks, and that is
all anybody needs to use one: which inputs are required, what each one is for,
what type it takes, and what comes back out.

Read from the module's own `.tf` files with the same parser the editor uses, so
what the catalog says about a module and what the editor says are the same
thing. A catalog whose description drifts from the code is worse than no
catalog: somebody trusts it once and stops checking.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backsight.engine.hcl.document import Document
from backsight.engine.hcl.navigation import blocks

README = ("README.md", "readme.md", "README.markdown")


@dataclass(frozen=True)
class Input:
    """One `variable` block, as somebody calling the module sees it."""

    name: str
    type: str = ""
    description: str = ""
    default: str = ""
    sensitive: bool = False

    @property
    def is_required(self) -> bool:
        """No default means the module will not plan without it."""
        return not self.default


@dataclass(frozen=True)
class Output:
    """One `output` block, which is what a caller gets back."""

    name: str
    description: str = ""
    sensitive: bool = False


@dataclass(frozen=True)
class Module:
    """One module in the catalog, by its own interface."""

    name: str
    path: Path
    inputs: tuple[Input, ...] = ()
    outputs: tuple[Output, ...] = ()
    about: str = ""
    unreadable: str = ""

    @property
    def required(self) -> tuple[Input, ...]:
        return tuple(one for one in self.inputs if one.is_required)

    @property
    def summary(self) -> str:
        needed = len(self.required)
        gives = len(self.outputs)
        return (
            f"{needed} required input{'' if needed == 1 else 's'} · "
            f"{gives} output{'' if gives == 1 else 's'}"
        )

    def matches(self, term: str) -> bool:
        wanted = term.strip().lower()
        if not wanted:
            return True
        haystack = " ".join((self.name, self.about, *[one.name for one in self.inputs])).lower()
        return all(word in haystack for word in wanted.split())

    def call(self, *, source: str = "", name: str = "") -> str:
        """A `module` block that calls this one, with every required input.

        Required inputs first and in the module's own order, each a placeholder
        so the caller tabs through exactly what they must decide. Optional ones
        are left out: a call carrying every optional argument at its default is
        a call nobody can read.
        """
        called = name or self.name.replace("-", "_")
        where = source or f"./{self.path.name}"
        lines = [f'module "${{1:{called}}}" {{', f'  source = "{where}"']
        width = max((len(one.name) for one in self.required), default=0)
        for number, one in enumerate(self.required, start=2):
            lines.append(f"  {one.name.ljust(width)} = {_placeholder(one, number)}")
        lines.append("}")
        return "\n".join(lines) + "\n"


def _placeholder(one: Input, number: int) -> str:
    """A placeholder shaped like the type the module asked for."""
    said = one.type.strip().lower()
    if said.startswith(("list", "set", "tuple")):
        return f"[${{{number}}}]"
    if said.startswith(("map", "object")):
        return f"{{\n    ${{{number}}}\n  }}"
    if said in ("number", "bool"):
        return f"${{{number}:{'0' if said == 'number' else 'false'}}}"
    return f'"${{{number}}}"'


def _string(value: str) -> str:
    """A quoted HCL string with its quotes taken off."""
    said = value.strip()
    if said.startswith('"') and said.endswith('"') and len(said) > 1:
        return said[1:-1]
    return said


def _argument(body: str, name: str) -> str:
    """One `name = value` out of a block's body, as written."""
    for line in body.splitlines():
        said = line.strip()
        if said.startswith(f"{name} ") or said.startswith(f"{name}="):
            _, _, value = said.partition("=")
            return value.strip()
    return ""


def read(path: Path) -> Module:
    """One module directory, by its variables and outputs."""
    directory = Path(path)
    inputs: list[Input] = []
    outputs: list[Output] = []
    unreadable = ""

    for file in sorted(directory.glob("*.tf")):
        try:
            document = Document.read(file)
        except (OSError, ValueError) as refused:
            unreadable = str(refused)
            continue
        for block in blocks(document.text.encode("utf-8")):
            if not block.labels:
                continue
            body = _body_of(document.text, block)
            if block.type == "variable":
                inputs.append(
                    Input(
                        name=block.labels[0],
                        type=_argument(body, "type"),
                        description=_string(_argument(body, "description")),
                        default=_argument(body, "default"),
                        sensitive=_argument(body, "sensitive") == "true",
                    )
                )
            elif block.type == "output":
                outputs.append(
                    Output(
                        name=block.labels[0],
                        description=_string(_argument(body, "description")),
                        sensitive=_argument(body, "sensitive") == "true",
                    )
                )

    return Module(
        name=directory.name,
        path=directory,
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        about=_about(directory),
        unreadable=unreadable,
    )


def _body_of(text: str, block) -> str:
    """The lines of one block, from the span the parser already worked out.

    Counted braces would get this wrong on a brace inside a string, and the
    parser has the answer — `first` and `last` are 1-based, as a person counts.
    """
    lines = text.splitlines()
    return "\n".join(lines[max(0, block.first - 1) : block.last])


def _about(directory: Path) -> str:
    """The first paragraph of the README, which is what a module says it is."""
    for name in README:
        found = directory / name
        if not found.is_file():
            continue
        try:
            text = found.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""
        paragraphs = [
            part.strip()
            for part in text.split("\n\n")
            if part.strip() and not part.strip().startswith("#")
        ]
        return " ".join(paragraphs[0].split()) if paragraphs else ""
    return ""


def catalog(root: Path) -> list[Module]:
    """Every module in a directory of them.

    A module is a directory with at least one `.tf` file in it. One level deep,
    because a catalog is a list of modules rather than a tree to go exploring.
    """
    base = Path(root)
    if not base.is_dir():
        return []
    found = []
    for directory in sorted(base.iterdir()):
        if directory.is_dir() and any(directory.glob("*.tf")):
            found.append(read(directory))
    return found


def as_entries(modules: list[Module], *, source: str = "") -> list:
    """Catalog modules as library entries, so one search finds both.

    FR-SCH-14's point: where an approved internal module exists for the thing
    somebody is writing, it should be in front of them at the same moment as
    the raw resource type — not in a separate place they have to remember to
    look. So a module is an entry like any other, and the library is the one
    place to look.
    """
    from backsight.engine.library.entry import Entry, Kind, Source

    return [
        Entry(
            name=f"{module.name} (module)",
            kind=Kind.SNIPPET,
            body=module.call(source=f"{source}//{module.name}" if source else ""),
            about=module.about or f"A module. {module.summary}.",
            tags=("module", "catalog"),
            source=Source.SHARED,
            path=module.path,
        )
        for module in modules
        if not module.unreadable
    ]
