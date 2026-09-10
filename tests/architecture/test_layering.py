"""The layers are a rule, not a folder arrangement.

A directory called `engine` proves nothing. These are the checks that make the
name true: what each layer may import, and that the engine can be imported on a
machine with no GTK on it at all.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "src" / "backsight"

# Available to every layer. `presentation` is the words a person reads and
# `actor` is who did something; both are vocabulary rather than machinery, and a
# layer that could not name them would carry its own version of each.
BASE = {"presentation", "actor"}

# Read top to bottom: each layer may import the ones already listed above it.
# `BASE` is added to every entry below.
ALLOWED = {
    "presentation": set(),
    "hcl": {"presentation"},
    "text": {"presentation"},
    "workspace": {"presentation", "hcl"},
    # Completion works out where the cursor is by reading the syntax tree, so
    # schema sits above hcl. No cycle: hcl knows nothing about schemas.
    "schema": {"presentation", "hcl"},
    "runner": {"presentation"},
    # Stacks parse, validate and graph entirely offline — FR-STK-09 — so this
    # layer reaches nothing. Not even the workspace: a stack is a deployable
    # unit with a declared path, and discovering directories is a different
    # question.
    "stacks": {"presentation"},
    # What is on screen and how it is reached. Nothing above it, because a panel
    # must be describable without a plan, a schema or a container.
    "settings": {"presentation"},
    "layout": {"presentation", "settings"},
    # The emulator is driven by running a container, and nothing else.
    "sandbox": {"presentation", "runner", "plan", "schema"},
    "vcs": {"presentation", "runner"},
    # A passing run has no location in the results stream, so the gutter has
    # to read the test file itself. No cycle: hcl knows nothing about tests.
    "tests": {"presentation", "runner", "hcl"},
    # Evaluating an expression means running the engine, so this cannot sit in
    # insight, which reads documents and never spawns anything.
    "console": {"presentation", "runner"},
    "plan": {"presentation", "runner", "workspace"},
    # Snippets, examples, recipes and runbooks. It reads the provider schema to
    # generate an entry per resource type, and nothing else — an entry is text
    # with placeholders, so it needs no plan, no workspace and no engine.
    "library": {"presentation", "schema"},
    # What this machine can authenticate as. It reads two INI files and writes
    # a log, and reaches nothing — least of all the network. The one thing it
    # promises is that no value which could be a secret leaves it, and a layer
    # that imports nothing is the cheapest way to keep that true.
    "credentials": {"presentation"},
    # What a policy set says about a change, and what it costs to make it. Both
    # read a plan; neither reaches anything else.
    "policy": {"presentation", "runner", "plan"},
    # Modules somebody already wrote. Read with the same parser the editor
    # uses, so what the catalog says about a module and what the editor says
    # cannot drift apart.
    "catalog": {"presentation", "hcl", "library"},
    # Anything that has to combine sources to answer a question sits here. Hover
    # needs the schema for the type and the plan for whether the attribute forces
    # replacement, and neither of those layers may reach into the other.
    "insight": {"presentation", "hcl", "workspace", "schema", "plan", "vcs"},
    # Rewriting goes through the syntax tree and is checked by a plan. It may
    # not reach into insight: a verdict is something you show, not something a
    # refactor consults.
    "refactor": {"presentation", "hcl", "workspace", "plan", "runner"},
}

# What the engine must never need. The app layer may import any of them.
TOOLKIT = ("gi", "gi.repository")


ALLOWED = {layer: allowed | BASE for layer, allowed in ALLOWED.items()}


def engine_modules() -> list[Path]:
    return sorted((PACKAGE / "engine").rglob("*.py"))


def imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_the_engine_never_imports_the_toolkit():
    for path in engine_modules():
        for name in imported_names(path):
            root = name.split(".")[0]
            assert root not in TOOLKIT, f"{path.relative_to(ROOT)} imports {name}"


def test_the_engine_imports_with_no_toolkit_installed():
    """Not importing `gi` in source is weaker than not needing it at run time."""
    script = (
        "import sys;"
        "sys.modules['gi'] = None;"
        "import backsight.engine.actor, backsight.engine.hcl.document,"
        " backsight.engine.presentation.language;"
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_each_engine_layer_imports_only_what_it_may():
    for layer, allowed in ALLOWED.items():
        directory = PACKAGE / "engine" / layer
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.py")):
            for name in imported_names(path):
                if not name.startswith("backsight.engine."):
                    continue
                other = name.split(".")[2]
                if other == layer:
                    continue
                assert other in allowed, (
                    f"{path.relative_to(ROOT)} reaches into {other}, which {layer} may not import"
                )


def test_every_engine_layer_is_declared():
    """A new directory under engine/ has to be given a rule before it is used."""
    on_disk = {
        d.name for d in (PACKAGE / "engine").iterdir() if d.is_dir() and not d.name.startswith("__")
    }
    undeclared = on_disk - set(ALLOWED)
    assert not undeclared, f"engine layers with no import rule: {sorted(undeclared)}"


def test_every_font_falls_back_to_something_the_desktop_has():
    """The design system picks IBM Plex and says why: its sans and mono share a
    skeleton, which keeps the tree and the buffer feeling like one surface.

    That is a deliberate choice rather than the earlier rule of setting no font
    at all — but it only holds if the app degrades sanely on a machine without
    Plex installed, so every stack must end in a generic family.
    """
    css = (PACKAGE / "app" / "theme" / "components.css").read_text(encoding="utf-8")
    families = re.findall(r"font-family:\s*([^;]+);", css)
    assert families, "the sheet sets no font at all"
    for stack in families:
        assert stack.strip().endswith(("sans-serif", "monospace")), stack
