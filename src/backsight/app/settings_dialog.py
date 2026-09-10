"""Preferences, in the words a person would use rather than the keys we store.

Every row was showing its own machine notation — a value reading `single_click`,
and under it `default: on · user: off  ← in effect`. Both are true and neither
is for a reader. The key is our name for the setting, the layer names are our
storage, and the arrow is our syntax.

So a value is a phrase, a title is a sentence fragment, and provenance appears
only when it is *load-bearing*: a setting the workspace file is overriding is
the one case where somebody changes a switch and nothing happens, and then a
plain sentence says which file to look in.

The dialog edits a file, and the file is the source of truth — it can be
committed to a repository, which is the only realistic way a platform team
distributes conventions. So the header offers to open it directly: this audience
edits config files for a living, and making them hunt for it would be strange.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from backsight.app.theme import tokens
from backsight.engine.settings import writing
from backsight.engine.settings.keys import Keymap
from backsight.engine.settings.layers import ORDER, Settings

# Grouped the way the dialog is, rather than alphabetically. Each carries
# an icon because a preferences page without one draws a broken image.
GROUPS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "Files",
        "folder-symbolic",
        "What a click in the file rail does, and what comes back when you reopen.",
        (
            "files.open_on",
            "files.preview_tabs",
            "files.promote_preview_on",
            "session.restore",
            "tabs.new_tab_position",
            "tabs.middle_click_closes",
            "tabs.confirm_close_unsaved",
            "library.shared_path",
            "catalog.path",
            "catalog.source",
            "conventions.naming",
            "conventions.tags",
            "aws.profile",
        ),
    ),
    (
        "Editor",
        "text-editor-symbolic",
        "Trimming and the final newline are on. Neither can change what a file means.",
        (
            "editor.font_family",
            "editor.tab_size",
            "editor.show_line_numbers",
            "editor.word_wrap",
            "editor.wrap_column",
            "editor.show_whitespace",
            "editor.rulers",
            "editor.hover_popups",
            "editor.trim_trailing_whitespace_on_save",
            "editor.ensure_final_newline",
            "editor.close_brackets",
            "editor.autosave",
            # What a tab and a rail row say about each file. These are settings
            # about the editor, and a page of their own left the Editor page
            # describing only half of it.
            "tabs.indicators.vcs",
            "tabs.indicators.plan_impact",
            "tabs.indicators.unsaved",
            "tabs.indicators.clear_plan_on_edit",
            "rail.indicators.vcs",
            "rail.indicators.plan_counts",
        ),
    ),
    (
        "Terraform",
        "utilities-terminal-symbolic",
        "Backsight never rewrites a file you did not ask it to rewrite.",
        (
            "terraform.binary",
            "terraform.format_on_save",
            "terraform.plan_on_save",
            "terraform.plan_debounce_ms",
            # What it works out on its own, and what it waits to be asked for.
            # Analysis *is* Terraform: a page of its own separated a setting
            # from the thing it is about.
            "analysis.value_completion",
            "analysis.exposure_on_edit",
            "analysis.convergence_on_save",
            "analysis.drift_every_minutes",
            "analysis.check_provider_versions",
            "docs.mirror_providers",
            "policy.scanner",
        ),
    ),
    (
        "Appearance",
        "preferences-desktop-appearance-symbolic",
        "The application follows the desktop unless told otherwise.",
        (
            "appearance.color_scheme",
            "appearance.editor_scheme_light",
            "appearance.editor_scheme_dark",
        ),
    ),
)


# The settings whose values are a fixed set. Anything not listed here is a
# switch, a number or free text, decided from the default's type — a value with
# four valid answers should never be a box somebody can typo into.
CHOICES: dict[str, tuple[str, ...]] = {
    "files.open_on": ("single_click", "double_click"),
    "files.promote_preview_on": ("edit", "double_click"),
    "tabs.new_tab_position": ("after_current", "end"),
    "tabs.indicators.vcs": ("icon", "none"),
    "tabs.indicators.plan_impact": ("icon", "none"),
    "tabs.indicators.unsaved": ("dot", "asterisk", "none"),
    "rail.indicators.vcs": ("letter", "dot", "none"),
    "appearance.color_scheme": ("follow_system", "light", "dark"),
}

# Values that are no longer offered, and the choice each now behaves as. Shown
# as the first option, "never" would claim the opposite of what it does.
RETIRED: dict[tuple[str, str], str] = {
    ("files.promote_preview_on", "never"): "double_click",
}

# What each stored value is called on screen. `single_click` is how we write it
# down; "a single click" is what somebody choosing it is choosing.
WORDS: dict[str, str] = {
    "single_click": "A single click",
    "double_click": "A double click",
    "edit": "When you type in it",
    "after_current": "Next to the current tab",
    "end": "At the end of the row",
    "icon": "An icon",
    "letter": "A letter",
    "dot": "A dot",
    "asterisk": "An asterisk",
    "none": "Nothing",
    "follow_system": "Follow the desktop",
    "light": "Light",
    "dark": "Dark",
    "backsight-light": "Backsight light",
    "backsight-dark": "Backsight dark",
}

# What each setting is called, and — where the name alone leaves a real
# question — one sentence answering it. A key is our storage; a title is a
# question the reader can answer.
TITLES: dict[str, tuple[str, str]] = {
    "files.open_on": (
        "Open a file from the rail with",
        "Otherwise one click previews it, and the next preview replaces it.",
    ),
    "files.preview_tabs": (
        "Reuse the tab you are in",
        "Opening replaces what is in front. Keep this one to open two at once.",
    ),
    "files.promote_preview_on": ("Keep a previewed file open", "A double click always does."),
    "session.restore": ("Reopen the last files on launch", ""),
    "catalog.path": (
        "Module catalog folder",
        "A folder of Terraform modules. Each one appears in the library, ready to call.",
    ),
    "catalog.source": (
        "What a module call should point at",
        "Blank uses a relative path, which is right for a catalog inside the workspace.",
    ),
    "conventions.naming": (
        "How resources should be named",
        "Use {name} and {environment}. A generated snippet arrives with it filled in.",
    ),
    "conventions.tags": (
        "Tags every resource carries",
        "key=value pairs, separated by commas. Only added where a snippet already tags.",
    ),
    "aws.profile": (
        "AWS profile",
        "Blank works it out: the default profile applies, and one named read-only reads.",
    ),
    "library.shared_path": (
        "Shared library folder",
        "A directory of entries your team shares, usually a cloned repository.",
    ),
    "tabs.new_tab_position": ("Put a new tab", ""),
    "tabs.middle_click_closes": ("Middle click closes a tab", ""),
    "tabs.confirm_close_unsaved": ("Ask before closing an unsaved file", ""),
    "tabs.indicators.vcs": ("Mark a tab whose file git has changed with", ""),
    "tabs.indicators.plan_impact": ("Mark a tab the plan touches with", ""),
    "tabs.indicators.unsaved": ("Mark an unsaved tab with", ""),
    "tabs.indicators.clear_plan_on_edit": (
        "Clear plan marks when you type",
        "A plan mark left over from before an edit is a confident lie.",
    ),
    "rail.indicators.vcs": ("Mark a changed file in the rail with", ""),
    "rail.indicators.plan_counts": (
        "Show plan counts in the rail",
        "How many resources each file creates, changes or destroys.",
    ),
    "editor.font_family": ("Editor font", "Anything monospaced. Blank uses the shipped default."),
    "editor.tab_size": (
        "Indent width",
        "Only used when a file has no indentation to read — the file always wins.",
    ),
    "editor.show_line_numbers": ("Line numbers", ""),
    "editor.word_wrap": ("Wrap long lines", ""),
    "editor.wrap_column": ("Wrap and ruler column", ""),
    "editor.show_whitespace": ("Show spaces and tabs", ""),
    "editor.rulers": ("Show the column ruler", ""),
    "editor.hover_popups": (
        "Explain a finding on hover",
        "Off means the gutter mark is the only place a finding is explained.",
    ),
    "editor.trim_trailing_whitespace_on_save": ("Trim trailing spaces when saving", ""),
    "editor.ensure_final_newline": ("End the file with a newline", ""),
    "editor.close_brackets": ("Close brackets and quotes as you type", ""),
    "editor.autosave": ("Save as you type", ""),
    "appearance.color_scheme": ("Light or dark", ""),
    "appearance.editor_scheme_light": ("Editor colours in light mode", ""),
    "appearance.editor_scheme_dark": ("Editor colours in dark mode", ""),
    "terraform.binary": ("Command to run", "`tofu` for OpenTofu, `terraform` for Terraform."),
    "terraform.format_on_save": (
        "Reformat when saving",
        "Off, because reformatting somebody's file for them is a change they did not ask for.",
    ),
    "terraform.plan_on_save": ("Plan when you save", ""),
    "terraform.plan_debounce_ms": (
        "Wait before planning",
        "Milliseconds. A save inside the wait restarts it, so a burst of saves plans once.",
    ),
    "analysis.value_completion": ("Suggest completions as you type", ""),
    "analysis.exposure_on_edit": ("Check public access with every plan", ""),
    "analysis.convergence_on_save": (
        "Rehearse the plan when you save",
        "Off, because it starts a container.",
    ),
    "analysis.check_provider_versions": (
        "Check for newer provider versions",
        "The only thing here that reaches the network. Off unless you ask for it.",
    ),
    "policy.scanner": (
        "Policy scanner",
        "Whatever is on your PATH. Nothing is bundled.",
    ),
    "docs.mirror_providers": (
        "Mirror provider documentation",
        "Fetched once per resource and kept, so it works offline afterwards.",
    ),
    "analysis.drift_every_minutes": (
        "Check for drift every",
        "Minutes, or zero for never. Each check asks the provider about every resource.",
    ),
}

# What to say when a value is coming from somewhere the reader did not set it.
# Only these two, and only when they are winning: the default winning is not
# news, and the user layer winning is the person's own choice being honoured.
ELSEWHERE = {
    "workspace": "Set by this workspace's .backsight/settings.toml",
    "language": "Set by your HCL settings file",
}


# A coupled setting warns where it is set, not in documentation nobody reads —
# and only when the combination is actually reached.
# None today: a single click that opens keeps every file it opens whatever the
# reuse setting says, so the one pairing that used to bite no longer interacts.
COUPLINGS: tuple[tuple[str, object, str, object, str], ...] = ()


def warnings_for(settings: Settings) -> list[str]:
    """Any combination worth saying something about, right now."""
    return [
        message
        for first, first_value, second, second_value, message in COUPLINGS
        if settings.get(first) == first_value and settings.get(second) == second_value
    ]


def warning_on(settings: Settings, key: str) -> str:
    """The warning for the row it is about, or nothing.

    A coupling is between two settings and belongs on both of them. It was a
    toast with no timeout, which put a permanent notice in the corner of a
    dialog whose rows are the thing it is talking about.
    """
    if key == "editor.font_family":
        said = font_warning(settings)
        if said:
            return said
    for first, first_value, second, second_value, message in COUPLINGS:
        if key not in (first, second):
            continue
        if settings.get(first) == first_value and settings.get(second) == second_value:
            return message
    return ""


def font_warning(settings: Settings) -> str:
    """Says when the editor is not being drawn in the font this names.

    **A font that silently substitutes is a design that silently does not
    exist.** Neither of the two families this was drawn against is installed on
    a stock Debian, and every screenshot the project ever took of itself was in
    a third one nobody chose — including the ones in its own README.
    """
    wanted = str(settings.get("editor.font_family", "") or "").strip()
    if wanted and tokens.installed(wanted):
        return ""
    drawn, as_chosen = tokens.in_use("mono")
    if as_chosen and not wanted:
        return ""
    asked = wanted or tokens.WANTED["mono"]
    if drawn == asked:
        return ""
    return f"{asked} is not installed. Falling back to {drawn}."


def provenance(settings: Settings, key: str) -> str:
    """Where the value came from, when that is worth saying — otherwise nothing.

    "Why is my setting not applying" only has a surprising answer when a file
    the person did not open is winning. Listing every layer for every row put
    `default: on · user: off  ← in effect` under thirty-eight controls, which is
    our storage model printed into somebody else's window.
    """
    return ELSEWHERE.get(settings.source(key), "")


def shown(key: str, value: object) -> str:
    """One value, as a phrase rather than as the token we store it under."""
    if isinstance(value, bool):
        return "On" if value else "Off"
    return WORDS.get(str(value), str(value))


def title_of(key: str) -> str:
    """What the setting is called. Never the key with its underscores removed."""
    found = TITLES.get(key)
    if found is not None:
        return found[0]
    return key.rsplit(".", 1)[-1].replace("_", " ").capitalize()


def description_of(key: str) -> str:
    """The sentence under the title, where the title leaves a real question."""
    found = TITLES.get(key)
    return found[1] if found is not None else ""


class SettingsDialog(Adw.PreferencesWindow):
    """The dialog, which is a view over a file."""

    def __init__(
        self,
        settings: Settings,
        *,
        parent: Gtk.Window | None = None,
        open_file: Callable[[], None] | None = None,
        keymap: Keymap | None = None,
        on_rebind: Callable[[str, str | None], None] | None = None,
        on_change: Callable[[str, object], None] | None = None,
    ) -> None:
        super().__init__(title="Preferences", transient_for=parent, modal=True)
        self.settings = settings
        self._on_change = on_change
        # Every row, so a change can rewrite the others rather than leaving
        # them describing the state before it.
        self._rows: dict[str, Adw.PreferencesRow] = {}

        # **Five pages.** There were eight, and three of them were slices of
        # another: tabs and indicators are editor settings, and analysis is
        # Terraform. Eight tabs along the bottom of a preferences window is a
        # menu bar wearing a different coat.
        for title, icon, description, keys in GROUPS:
            # The page title is what the switcher along the bottom shows, and
            # it truncates: "Files and tabs" arrived as "Files and ta…". The
            # group heading inside has the room to say more.
            page = Adw.PreferencesPage(title=title, icon_name=icon)
            group = Adw.PreferencesGroup(title=title, description=description or None)
            for key in keys:
                group.add(self._row(key))
            page.add(group)
            if title == "Files" and open_file is not None:
                # Where it belongs rather than on a page of its own: it is one
                # button, and a page for one button is a page.
                button = Gtk.Button(label="Open settings file")
                button.set_valign(Gtk.Align.CENTER)
                button.connect("clicked", lambda *_: open_file())
                page.add(_the_file_group(button))
            self.add(page)

        self.add(_keys_page(keymap or Keymap.build(), on_rebind))

    def _row(self, key: str) -> Adw.PreferencesRow:
        """One setting, as a control rather than a label.

        The subtitle is the sentence the title left unanswered, or — where a
        file the person did not open is winning — which file that is. It is
        never both, because a row with two lines under it is a paragraph.
        """
        title = title_of(key)
        subtitle = self._second_line(key)
        value = self.settings.get(key)

        if key in CHOICES:
            options = CHOICES[key]
            row = Adw.ComboRow(title=title, subtitle=subtitle)
            row.set_model(Gtk.StringList.new([shown(key, option) for option in options]))
            value = RETIRED.get((key, value), value)
            row.set_selected(options.index(value) if value in options else 0)
            row.connect(
                "notify::selected",
                lambda widget, _p, k=key, o=options: self._changed(k, o[widget.get_selected()]),
            )
            self._rows[key] = row
            return row

        if isinstance(value, bool):
            row = Adw.SwitchRow(title=title, subtitle=subtitle, active=value)
            row.connect(
                "notify::active", lambda widget, _p, k=key: self._changed(k, widget.get_active())
            )
            self._rows[key] = row
            return row

        if isinstance(value, int | float):
            low, high, step = _numeric(key, float(value))
            row = Adw.SpinRow.new_with_range(low, high, step)
            row.set_title(title)
            row.set_subtitle(subtitle)
            row.set_value(float(value))
            row.connect(
                "notify::value", lambda widget, _p, k=key: self._changed(k, int(widget.get_value()))
            )
            self._rows[key] = row
            return row

        # An `Adw.ActionRow` with an entry in it rather than an `Adw.EntryRow`,
        # for one reason: an `Adw.EntryRow` has no subtitle, so everything a row
        # had to say went onto a tooltip. **The font row's warning is the case
        # that settles it** — *JetBrains Mono is not installed, falling back to
        # DejaVu Sans Mono* is not something to hide behind a hover.
        #
        # And an empty field says **Not set** rather than sitting blank: a blank
        # control beside a grey label reads as disabled.
        entry = Gtk.Entry(text=str(value or ""), width_chars=18)
        entry.set_placeholder_text("Not set")
        entry.set_valign(Gtk.Align.CENTER)
        entry.connect("activate", lambda widget, k=key: self._changed(k, widget.get_text().strip()))
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        row.add_suffix(entry)
        row.set_activatable_widget(entry)
        self._rows[key] = row
        return row

    def _changed(self, key: str, value: object) -> None:
        """Writes it, and tells whoever is listening so it takes effect now.

        Written to the user layer only. The workspace file is committed and
        shared, and a switch here may not edit a colleague's editor.
        """
        try:
            writing.remember(key, value)
        except (OSError, ValueError) as refused:
            # Long, because a setting that did not save is worth reading twice,
            # but not forever: nothing in a dialog should outlive the dialog.
            self.add_toast(Adw.Toast(title=f"Could not save that: {refused}", timeout=10))
            return
        # The dialog's own copy has to move too. Without this every other row
        # keeps describing the state before this change, and the coupling
        # warnings are computed against a settings object that is now wrong.
        self.settings.layers.setdefault("user", {})[key] = value
        self._resubtitle()
        if self._on_change is not None:
            self._on_change(key, value)

    def _second_line(self, key: str) -> str:
        """A live warning first, then where the value came from, then help.

        Never two of them: a row with two lines under it is a paragraph.
        """
        return (
            warning_on(self.settings, key) or provenance(self.settings, key) or description_of(key)
        )

    def _resubtitle(self) -> None:
        """Rewrites each row's second line against the settings as they are now."""
        for key, row in self._rows.items():
            row.set_subtitle(self._second_line(key))


def _numeric(key: str, value: float) -> tuple[float, float, float]:
    """Sensible bounds for a number, so a spin box cannot reach nonsense."""
    if key.endswith("_ms"):
        return (0.0, 10_000.0, 100.0)
    if key.endswith("max_width"):
        return (60.0, 600.0, 10.0)
    if key.endswith("wrap_column"):
        return (40.0, 200.0, 1.0)
    return (1.0, 16.0, 1.0)


def _the_file_group(button: Gtk.Widget) -> Adw.PreferencesGroup:
    """The one thing this audience will look for, on the page it belongs to.

    They edit config files for a living, so hunting for the file would be
    strange — and a page of its own for a single button is a page.
    """
    group = Adw.PreferencesGroup(
        title="Settings are a file",
        description=(
            "The file is the source of truth. Commit "
            f"`{ORDER[2]}` settings to a repository to share conventions."
        ),
    )
    row = Adw.ActionRow(title="Open settings file")
    row.add_suffix(button)
    group.add(row)
    return group


def _keys_page(
    keymap: Keymap, on_rebind: Callable[[str, str | None], None] | None
) -> Adw.PreferencesPage:
    """Every command and its key, grouped as the keyboard reference groups them.

    A binding is edited here and written to the settings file, because a keymap
    nobody can change is a keymap that fits one person.
    """
    page = Adw.PreferencesPage(title="Keys", icon_name="preferences-desktop-keyboard-symbolic")

    conflicts = keymap.conflicts()
    if conflicts:
        # Reported rather than resolved: choosing for someone silently loses a
        # binding they meant to have.
        group = Adw.PreferencesGroup(title="Conflicts")
        for conflict in conflicts:
            group.add(Adw.ActionRow(title=str(conflict)))
        page.add(group)

    for section, commands in sorted(keymap.sections().items()):
        group = Adw.PreferencesGroup(title=section)
        for command in commands:
            row = Adw.ActionRow(
                title=command.label,
                subtitle="cannot be unbound" if command.is_floor else "",
            )
            entry = Gtk.Entry(text=command.accelerator or "", width_chars=16)
            entry.set_valign(Gtk.Align.CENTER)
            entry.add_css_class("tf-mono")
            entry.set_editable(on_rebind is not None)
            if on_rebind is not None:
                entry.connect(
                    "activate",
                    lambda widget, action=command.action: on_rebind(
                        action, widget.get_text().strip() or None
                    ),
                )
            row.add_suffix(entry)
            group.add(row)
        page.add(group)
    return page
