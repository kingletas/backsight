"""Each workspace's layout, remembered where it belongs to the person.

FR-APP-14. A module repository and a root-module repository want different
layouts, and one global setting forces one of them to be wrong.

**Not in the workspace.** `.backsight/settings.toml` is meant to be committed so
a team shares conventions; which rails one person has open is not a convention,
and putting it there would make everyone's editor state a reviewable change.
This lives in the user's own state directory, keyed by the workspace path.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from backsight.engine.layout.panels import Layout, Visibility

FILE = "layouts.toml"


def directory(home: Path | None = None) -> Path:
    """The XDG state directory, which is for exactly this kind of thing.

    State is what a program remembers to be pleasant, and what nobody would
    miss if it were deleted — as distinct from config, which the person wrote.
    """
    if home is not None:
        # An explicit home wins over the environment. Without this a test would
        # write into the real state directory whenever XDG_STATE_HOME is set.
        return Path(home) / ".local" / "state" / "backsight"
    root = os.environ.get("XDG_STATE_HOME")
    base = Path(root) if root else Path.home() / ".local" / "state"
    return base / "backsight"


def read(home: Path | None = None) -> dict[str, Layout]:
    """Every remembered layout. An unreadable file remembers nothing.

    A corrupt state file must never stop the application opening: the worst it
    may cost is the layout, which the person can set again in two clicks.
    """
    path = directory(home) / FILE
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return {}
    found: dict[str, Layout] = {}
    for workspace, states in document.items():
        if not isinstance(states, dict):
            continue
        found[workspace] = _layout(states)
    return found


def layout_for(workspace: Path, home: Path | None = None) -> Layout | None:
    """The layout last used in this workspace, or None if it has none."""
    return read(home).get(str(Path(workspace).resolve()))


def remember(workspace: Path, layout: Layout, home: Path | None = None) -> Path:
    """Writes this workspace's layout, leaving every other workspace alone."""
    path = directory(home) / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    every = read(home)
    every[str(Path(workspace).resolve())] = layout
    path.write_text(_document(every), encoding="utf-8")
    return path


def forget(workspace: Path, home: Path | None = None) -> None:
    """Drops one workspace, so resetting a layout really does reset it."""
    every = read(home)
    if every.pop(str(Path(workspace).resolve()), None) is None:
        return
    path = directory(home) / FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_document(every), encoding="utf-8")


def _layout(states: dict) -> Layout:
    """Reads one workspace's table, ignoring anything it does not recognise.

    A panel that no longer exists, or a state that never did, is skipped rather
    than raised: the file may have been written by an older or newer version.
    """
    found: dict[str, Visibility] = {}
    for name, value in states.items():
        try:
            found[name] = Visibility(value)
        except ValueError:
            continue
    layout = Layout.default()
    layout.states.update(found)
    return layout


def _key(workspace: str) -> str:
    """A path as a TOML basic string. A directory may contain a quote."""
    escaped = workspace.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _document(every: dict[str, Layout]) -> str:
    lines = ["# Written by Backsight. Layouts are per workspace — FR-APP-14.", ""]
    for workspace in sorted(every):
        lines.append(f"[{_key(workspace)}]")
        for name in sorted(every[workspace].states):
            lines.append(f'{name} = "{every[workspace].states[name].value}"')
        lines.append("")
    return "\n".join(lines)
