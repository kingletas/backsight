"""Changing a setting, which until now nothing could do.

The dialog showed every value as a label and the keymap held rebindings in
memory that were gone on the next launch — while its docstring said they were
written to the settings file. A preferences window that cannot change a
preference is a viewer.

Writes go to the **user** layer only. The workspace file is committed to a
repository and shared, so a checkbox in this window must never edit it: that
would change a colleague's editor without telling either of them.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from backsight.engine.settings import layers


def user_file(home: Path | None = None) -> Path:
    """The file a preference is written to — the same one `load` reads."""
    return layers.config_home(home) / "backsight" / "settings.toml"


def remember(key: str, value: Any, *, home: Path | None = None) -> None:
    """Sets one dotted key, leaving every other line in the file alone."""
    path = user_file(home)
    document = _read(path)
    _put(document, key.split("."), value)
    _write(path, document)


def forget(key: str, *, home: Path | None = None) -> None:
    """Removes one key, so the layer below it decides again.

    Empty tables are removed with it. A file left holding `[editor]` and
    nothing else reads as a setting somebody meant to make.
    """
    path = user_file(home)
    document = _read(path)
    _drop(document, key.split("."))
    _write(path, document)


def _read(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # A file that will not parse is not overwritten silently — the caller
        # asked to change one key, not to discard everything in it.
        if path.exists():
            raise
        return {}


def _write(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    beside = path.with_suffix(".toml.writing")
    beside.write_bytes(tomli_w.dumps(document).encode("utf-8"))
    os.replace(beside, path)


def _put(document: dict[str, Any], parts: list[str], value: Any) -> None:
    for part in parts[:-1]:
        found = document.get(part)
        if not isinstance(found, dict):
            found = {}
            document[part] = found
        document = found
    document[parts[-1]] = value


def _drop(document: dict[str, Any], parts: list[str]) -> None:
    if len(parts) == 1:
        document.pop(parts[0], None)
        return
    found = document.get(parts[0])
    if isinstance(found, dict):
        _drop(found, parts[1:])
        if not found:
            document.pop(parts[0], None)
