"""What a tab says about its file, within what the toolkit will actually draw.

The design draws four states on the edges of a tab — git on the left, plan impact
along the bottom, unsaved on the right, focus in the background and weight.

**`Adw.TabPage` is a GObject rather than a widget, so a tab cannot take a CSS
class and cannot have coloured edges.** What it has is two icon slots, a title
and a tooltip. Everything the design wants to *say* fits in those; the geometry
does not. See `docs/toolkit-notes.md` — a custom tab bar would buy the edges and
cost drag-to-reorder, drag-out-to-split and the tab overview.

So the states are carried by **shape and word**, which is what NFR-15 asks for
anyway: take the colour away and a triangle is still not a trash can.
"""

from __future__ import annotations

from backsight.engine.insight.file_status import FileStatus, Impact
from backsight.engine.vcs.git import Vcs

# Shape, not hue. Each of these is distinguishable in a greyscale screenshot.
VCS_ICONS = {
    Vcs.UNTRACKED: "document-new-symbolic",
    Vcs.MODIFIED: "document-edit-symbolic",
    Vcs.CONFLICTED: "dialog-warning-symbolic",
    Vcs.DELETED: "user-trash-symbolic",
}

# The plan's own four marks, shipped with the application rather than borrowed
# from the desktop's action set. Borrowed ones read as the action they usually
# perform: `list-add-symbolic` beside a filename is a **new tab** to anybody who
# has ever used one, whatever it was put there to mean. These are the shapes the
# gutter draws, so a tab and a line say the same thing the same way.
IMPACT_ICONS = {
    Impact.CREATE: "bs-plan-add-symbolic",
    Impact.CHANGE: "bs-plan-change-symbolic",
    Impact.REPLACE: "bs-plan-replace-symbolic",
    Impact.DESTROY: "bs-plan-destroy-symbolic",
}

VCS_WORDS = {
    Vcs.UNTRACKED: "new file",
    Vcs.MODIFIED: "modified",
    Vcs.CONFLICTED: "conflicted",
    Vcs.DELETED: "deleted from disk",
}

IMPACT_WORDS = {
    Impact.CREATE: "creates resources",
    Impact.CHANGE: "changes resources in place",
    Impact.REPLACE: "replaces resources",
    Impact.DESTROY: "destroys resources",
}


def vcs_icon(status: FileStatus) -> str | None:
    return VCS_ICONS.get(status.vcs)


def impact_icon(status: FileStatus) -> str | None:
    """Suppressed on an unreadable file, which has no meaningful plan state."""
    if not status.shows_impact:
        return None
    return IMPACT_ICONS.get(status.impact)


# What an unsaved tab is marked with. `none` is for anybody who reads the mark
# as clutter — the tooltip still says it, so the state is never only a symbol.
UNSAVED_MARKS = {"dot": " •", "asterisk": " *", "none": ""}


def title(name: str, status: FileStatus, *, letters: bool = False, unsaved: str = "dot") -> str:
    """The tab's text, with the unsaved mark and optionally the git letter.

    Letters mode is a setting rather than a hidden accessibility flag, and it is
    the only carrier that survives a screenshot with no icons at all.
    """
    prefix = f"{status.vcs.letter} " if letters and status.vcs.letter else ""
    suffix = UNSAVED_MARKS.get(unsaved, " •") if status.unsaved else ""
    return f"{prefix}{name}{suffix}"


def tooltip(path: str, status: FileStatus) -> str:
    """Everything the slots imply, in words, on one line each."""
    said = [path]
    if status.unreadable:
        said.append("cannot be read — not UTF-8")
        return "\n".join(said)
    if status.vcs in VCS_WORDS:
        said.append(VCS_WORDS[status.vcs])
    if status.unsaved:
        said.append("unsaved changes")
    if status.shows_impact:
        detail = IMPACT_WORDS.get(status.impact, "")
        summary = status.summary
        said.append(f"{detail} — {summary}" if summary else detail)
    return "\n".join(said)
