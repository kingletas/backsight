"""Settings, and which layer supplied the value in effect.

Four layers, each overriding the last **at the individual key**. Specify
it now or it gets decided accidentally by whichever loader runs last.

The part that matters as much as the precedence is being able to answer *why is
my setting not applying*. That question is otherwise unanswerable, and the answer
is nearly always a layer the person forgot exists — so every value knows where it
came from and what it beat.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Highest last: a later layer overrides an earlier one, key by key.
ORDER = ("default", "user", "workspace", "language")

WHERE = {
    "user": Path("~/.config/backsight/settings.toml"),
    "workspace": Path(".backsight/settings.toml"),
    "language": Path("~/.config/backsight/settings.hcl.toml"),
}

# Shipped defaults. The table, with its reasoning kept beside each one that
# is not obvious.
DEFAULTS: dict[str, Any] = {
    # Faster to browse, and safe because preview tabs are on.
    "files.open_on": "double_click",
    "files.preview_tabs": True,
    "files.promote_preview_on": "edit",
    # Auto-scrolling the rail under the user is disorienting and hard to undo.
    "tabs.new_tab_position": "after_current",
    "tabs.middle_click_closes": True,
    "tabs.confirm_close_unsaved": True,
    # An icon or nothing. `Adw.TabPage` is a GObject rather than a widget, so a
    # tab cannot take a CSS class and cannot have a coloured edge — "bar" was a
    # value nothing could ever draw. See `app/tab_marks.py`.
    "tabs.indicators.vcs": "icon",
    "tabs.indicators.plan_impact": "icon",
    "tabs.indicators.unsaved": "dot",
    # A stale plan marker is a confident lie.
    "tabs.indicators.clear_plan_on_edit": True,
    "rail.indicators.vcs": "letter",
    "rail.indicators.plan_counts": True,
    # Shown. The rail is how somebody finds a file, so opening with it folded
    # away is the workbench hiding its own navigation. "collapsed" sat here as
    # a default nothing read, and reading it started the app in that state.
    "layout.left_rail": "shown",
    "layout.change_map": "shown",
    "layout.remember_per_workspace": True,
    "appearance.color_scheme": "follow_system",
    "appearance.editor_scheme_light": "backsight-light",
    "appearance.editor_scheme_dark": "backsight-dark",
    "terraform.binary": "tofu",
    # Round-trip safety is a hard constraint; reformatting by default breaks it.
    "terraform.format_on_save": False,
    # The live plan is the product. Off by default would hide the differentiator.
    "terraform.plan_on_save": True,
    "terraform.plan_debounce_ms": 800,
    "analysis.value_completion": True,
    "analysis.exposure_on_edit": True,
    # Starts a container. Too expensive to be implicit.
    "analysis.convergence_on_save": False,
    # Minutes between background drift checks, or 0 for never. Off by default:
    # a refresh costs a provider call per resource, and starting that on its own
    # against somebody's account without being asked is not ours to decide.
    "analysis.drift_every_minutes": 0,
    # The only thing in this application that reaches the network. Off unless
    # asked for: an editor that phones a registry the first time it opens a
    # workspace is announcing that workspace without being told to.
    "analysis.check_provider_versions": False,
    "editor.tab_size": 4,
    # Both on: neither can change what a file means, and every other tool in
    # the chain assumes them.
    "editor.trim_trailing_whitespace_on_save": True,
    "editor.ensure_final_newline": True,
    "editor.word_wrap": False,
    "editor.show_whitespace": False,
    "editor.show_line_numbers": True,
    "editor.rulers": False,
    "editor.hover_popups": True,
    "editor.wrap_column": 100,
    "editor.autosave": False,
    "editor.close_brackets": True,
    "editor.font_family": "JetBrains Mono",
    "session.restore": True,
    # A directory of shared entries — usually a cloned git repository a
    # platform team distributes. Empty means you have none, which is the
    # ordinary case and not a fault.
    "library.shared_path": "",
    # Which AWS profile to use. Empty means work it out — the default profile
    # applies, and one that names itself read-only reads.
    "aws.profile": "",
    # Fetching a provider's own documentation, once per resource per version,
    # and keeping it. Off unless asked for: it reaches the network, and after
    # the first fetch it works on a plane.
    "docs.mirror_providers": False,
    # Which policy scanner to run. Whatever is on PATH — nothing is bundled,
    # and one that is not installed is a state rather than a failure.
    "policy.scanner": "checkov",
    # A folder of Terraform modules — a cloned repository, or a path in this
    # workspace. Nothing is fetched: a registry needs network and credentials,
    # and a folder is what a platform team can hand somebody today.
    "catalog.path": "",
    # What a generated call should use as its `source`. Empty means a relative
    # path, which is right for a catalog inside the workspace and wrong for one
    # that is cloned somewhere else.
    "catalog.source": "",
    # What a generated snippet's first placeholder should say, with `{name}`
    # and `{environment}` filled in. An HCL interpolation cannot go in it: a
    # placeholder default ends at its first `}`.
    "conventions.naming": "",
    # `key=value` pairs, filled into a snippet that already has a tags block.
    "conventions.tags": "",
}


@dataclass(frozen=True)
class Source:
    """One layer's answer for one key."""

    layer: str
    value: Any
    in_effect: bool = False


@dataclass
class Settings:
    """Every layer, flattened, with its provenance kept."""

    layers: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get(self, key: str, fallback: Any = None) -> Any:
        for layer in reversed(ORDER):
            values = self.layers.get(layer) or {}
            if key in values:
                return values[key]
        return DEFAULTS.get(key, fallback)

    def source(self, key: str) -> str:
        """Which layer the value in effect came from."""
        for layer in reversed(ORDER):
            if key in (self.layers.get(layer) or {}):
                return layer
        return "default"

    def explain(self, key: str) -> list[Source]:
        """Every layer's answer, and which one won.

        Show the winner *and* the losers. Showing only the winner
        leaves "why is my setting not applying" unanswerable.
        """
        winner = self.source(key)
        found = []
        for layer in ORDER:
            values = DEFAULTS if layer == "default" else (self.layers.get(layer) or {})
            if key in values:
                found.append(Source(layer=layer, value=values[key], in_effect=layer == winner))
        return found

    def keys(self) -> list[str]:
        seen = set(DEFAULTS)
        for values in self.layers.values():
            seen |= set(values)
        return sorted(seen)


def flatten(document: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """`{"files": {"open_on": "x"}}` becomes `{"files.open_on": "x"}`."""
    found: dict[str, Any] = {}
    for key, value in document.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            found.update(flatten(value, prefix=f"{path}."))
        else:
            found[path] = value
    return found


class Unreadable(Exception):
    """A settings file that will not parse, named so it can be reported."""

    def __init__(self, path: Path, detail: str) -> None:
        super().__init__(f"{path} could not be read: {detail}")
        self.path = path


def read(path: Path) -> dict[str, Any]:
    """One file, flattened. A missing file is empty; a broken one is an error.

    Silently ignoring a settings file somebody wrote is worse than refusing it —
    they will spend an afternoon wondering why it does nothing.
    """
    path = Path(path).expanduser()
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as handle:
            return flatten(tomllib.load(handle))
    except tomllib.TOMLDecodeError as error:
        raise Unreadable(path, str(error)) from error


def config_home(home: Path | None = None) -> Path:
    """Where the user layer lives, honouring `XDG_CONFIG_HOME`.

    The writer honoured it and the reader did not, so setting that variable
    sent a saved setting to one file and looked for it in another.
    """
    if home is not None:
        return Path(home).expanduser() / ".config"
    root = os.environ.get("XDG_CONFIG_HOME")
    return Path(root) if root else Path.home() / ".config"


def load(workspace: Path | None = None, *, home: Path | None = None) -> Settings:
    """The four layers, in order, from wherever each of them lives."""
    base = config_home(home)
    settings = Settings()
    settings.layers["default"] = dict(DEFAULTS)
    settings.layers["user"] = read(base / "backsight" / "settings.toml")
    if workspace is not None:
        settings.layers["workspace"] = read(Path(workspace) / ".backsight" / "settings.toml")
    settings.layers["language"] = read(base / "backsight" / "settings.hcl.toml")
    return settings
