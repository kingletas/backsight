"""What is in a directory somebody just opened.

FR-APP-02: root modules, backend configuration, provider requirements and the
lock file, worked out by reading the files rather than by asking the user.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backsight.engine.hcl import parse

# Directories that never hold a module worth listing. `.terraform` is a download
# cache, and a module found inside it is a copy of one already listed.
IGNORED = {".terraform", ".git", ".venv", "node_modules", "__pycache__"}

LOCK_FILE = ".terraform.lock.hcl"


@dataclass(frozen=True)
class Provider:
    """A provider a module asks for, and the version it actually got."""

    name: str
    source: str | None = None
    constraint: str | None = None
    locked_version: str | None = None


@dataclass(frozen=True)
class ModuleCall:
    """One `module "name" { source = ... }`, and where it was written."""

    name: str
    source: str
    declared_in: Path

    @property
    def is_local(self) -> bool:
        """A registry or git source names something outside this tree."""
        return self.source.startswith(".")

    def target(self) -> Path | None:
        return (self.declared_in.parent / self.source).resolve() if self.is_local else None


@dataclass
class Module:
    """One directory of Terraform, and what reading it says about it."""

    path: Path
    files: list[Path] = field(default_factory=list)
    backend: str | None = None
    providers: list[Provider] = field(default_factory=list)
    calls: list[ModuleCall] = field(default_factory=list)
    is_root: bool = True

    @property
    def name(self) -> str:
        return self.path.name

    def call(self, name: str) -> ModuleCall | None:
        return next((c for c in self.calls if c.name == name), None)

    @property
    def has_lock_file(self) -> bool:
        return (self.path / LOCK_FILE).is_file()

    def provider(self, name: str) -> Provider | None:
        return next((p for p in self.providers if p.name == name), None)


@dataclass
class Workspace:
    """A directory opened in the window, and every module under it."""

    path: Path
    modules: list[Module] = field(default_factory=list)

    @property
    def root_modules(self) -> list[Module]:
        return [m for m in self.modules if m.is_root]

    @property
    def is_terraform(self) -> bool:
        """Whether opening this directory found any Terraform at all."""
        return bool(self.modules)

    def module_at(self, path: Path) -> Module | None:
        return next((m for m in self.modules if m.path == path), None)


def discover(root: Path) -> Workspace:
    """Reads a directory and returns what it holds.

    A directory with `.tf` files in it is a module. It is a *root* module unless
    some other module names it as a source, because a module somebody calls is
    not one you plan from.
    """
    root = Path(root).resolve()
    modules = [_read_module(d) for d in sorted(_module_directories(root))]
    called = _called_paths(modules)
    for module in modules:
        module.is_root = module.path not in called
    return Workspace(path=root, modules=modules)


def _called_paths(modules: list[Module]) -> set[Path]:
    """Every directory some other module names as a source.

    Only local paths count. A registry or git source names something that is not
    in this tree, so it can never make a directory here a child module.
    """
    called: set[Path] = set()
    for module in modules:
        for call in module.calls:
            target = call.target()
            # A module that calls itself is still one you plan from. Counting
            # that as being called leaves a workspace with no root at all.
            if target is not None and target != module.path:
                called.add(target)
    return called


def _module_directories(root: Path) -> list[Path]:
    found = []
    for path in root.rglob("*.tf"):
        if any(part in IGNORED for part in path.relative_to(root).parts):
            continue
        if path.parent not in found:
            found.append(path.parent)
    return found


def _read_module(directory: Path) -> Module:
    module = Module(
        path=directory,
        files=sorted(
            p for p in directory.iterdir() if p.suffix in (".tf", ".tfvars") and p.is_file()
        ),
    )
    constraints: dict[str, Provider] = {}
    for path in module.files:
        if path.suffix != ".tf":
            continue
        source = path.read_bytes()
        body = parse.body_of(source)
        for block in parse.blocks(body, source):
            if block.type == "terraform":
                _read_terraform_block(block, module, constraints)
            elif block.type == "module" and block.labels:
                declared = parse.string_attribute(block.body, source, "source")
                if declared:
                    module.calls.append(
                        ModuleCall(name=block.labels[0], source=declared, declared_in=path)
                    )
    _apply_lock_file(directory, constraints)
    module.providers = [constraints[name] for name in sorted(constraints)]
    return module


def _read_terraform_block(
    block: parse.Block, module: Module, constraints: dict[str, Provider]
) -> None:
    for backend in block.blocks("backend"):
        if backend.labels:
            module.backend = backend.labels[0]
    for required in block.blocks("required_providers"):
        for name in required.attributes():
            entry = parse.object_attribute(required.body, required.source, name)
            constraints[name] = Provider(
                name=name, source=entry.get("source"), constraint=entry.get("version")
            )


def _apply_lock_file(directory: Path, constraints: dict[str, Provider]) -> None:
    """The lock file is the version in use; `required_providers` is only a range."""
    lock = directory / LOCK_FILE
    if not lock.is_file():
        return
    source = lock.read_bytes()
    body = parse.body_of(source)
    for block in parse.blocks(body, source, "provider"):
        if not block.labels:
            continue
        # The label is a full registry address; the short name is its last part.
        name = block.labels[0].rsplit("/", 1)[-1]
        version = parse.string_attribute(block.body, source, "version")
        existing = constraints.get(name)
        constraints[name] = Provider(
            name=name,
            source=existing.source if existing else block.labels[0],
            constraint=existing.constraint if existing else None,
            locked_version=version,
        )
