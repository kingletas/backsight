"""What Backsight is, said once, in the one place that can say it.

The stock dialog could not do this. `AdwAboutDialog` owns its icon, its version
pill and its row structure and sources most of it from appstream metainfo, so
it gave the most prominent band in the window to a version number and nowhere
said what the product does. It is still here, behind "Credits and legal", where
its licence rendering is worth having.

The three build facts exist because the first three questions on any bug report
against an infrastructure tool are which build, which Terraform, and whether
that combination is supported. One screenshot should answer all three.
"""

from __future__ import annotations

from collections.abc import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from backsight import __version__

WIDTH = 340

DESCRIPTION = (
    "Reads your state and your plan, and tells you what a change will "
    "actually cost before you run it."
)

# Not decoration. It is the only place the product explains its own premise,
# and the premise is the reason to prefer this over a terminal.
PREMISE = (
    "A backsight is the reading a surveyor takes back to a known point, to "
    "establish where they are before measuring forward."
)

# What this build has been run against. A constant, because it is a claim
# somebody made rather than something discoverable at runtime.
TESTED_AGAINST = "1.6 – 1.13"

NOT_FOUND = "not found"

ISSUES = "https://github.com/kingletas/backsight/issues/new"


class AboutDialog(Adw.Dialog):
    """The identity block, three facts, four actions, and the premise."""

    def __init__(
        self,
        *,
        version: str = "",
        commit: str = "",
        engine: str = "",
        icon: str = "com.kingletas.Backsight",
        on_shortcuts: Callable[[], None] | None = None,
        on_release_notes: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.set_content_width(WIDTH)
        self.set_title("About Backsight")
        self._on_shortcuts = on_shortcuts
        self._on_release_notes = on_release_notes
        self._version = version or __version__
        self._commit = commit
        self._engine = engine
        self._icon = icon
        self._rows_shown: list[str] = []

        header = Adw.HeaderBar()
        header.set_show_title(False)
        header.add_css_class("flat")

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        body.append(self._identity(icon))
        body.append(self._facts())
        body.append(self._actions())
        body.append(self._premise())

        layout = Adw.ToolbarView()
        layout.add_top_bar(header)
        layout.set_content(body)
        self.set_child(layout)

    @property
    def facts(self) -> dict[str, str]:
        """The three build facts, for anything checking what is shown."""
        return dict(self._facts_shown)

    @property
    def rows(self) -> list[str]:
        """The action rows, in order."""
        return list(self._rows_shown)

    @property
    def icon_name(self) -> str:
        """What the identity block draws. Never the generic document glyph."""
        return self._icon

    @property
    def says(self) -> list[str]:
        """Every sentence the dialog states in its own voice."""
        return [DESCRIPTION, PREMISE]

    def _identity(self, icon: str) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_margin_top(22)
        box.set_margin_bottom(16)
        box.set_margin_start(20)
        box.set_margin_end(20)

        mark = Gtk.Image.new_from_icon_name(icon)
        mark.set_pixel_size(56)
        box.append(mark)

        name = Gtk.Label(label="Backsight")
        name.add_css_class("tf-title")
        name.set_margin_top(10)
        box.append(name)

        says = Gtk.Label(label=DESCRIPTION, wrap=True, justify=Gtk.Justification.CENTER)
        says.add_css_class("tf-faint")
        says.add_css_class("tf-small")
        says.set_margin_top(6)
        box.append(says)
        return box

    def _facts(self) -> Gtk.Widget:
        # A Terraform that is not there says so rather than being hidden. The
        # absence is the useful information on a bug report.
        engine = f"{self._engine} detected" if self._engine else NOT_FOUND
        self._facts_shown = {
            "Version": f"{self._version} · {self._commit}" if self._commit else self._version,
            "Terraform": engine,
            "Tested against": TESTED_AGAINST,
        }
        group = Adw.PreferencesGroup()
        group.set_margin_start(14)
        group.set_margin_end(14)
        for name, value in self._facts_shown.items():
            row = Adw.ActionRow(title=name)
            shown = Gtk.Label(label=value)
            shown.add_css_class("tf-mono")
            shown.add_css_class("tf-small")
            if value == NOT_FOUND:
                shown.add_css_class("tf-nostate")
            row.add_suffix(shown)
            group.add(row)
        return group

    def _actions(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup()
        group.set_margin_start(14)
        group.set_margin_end(14)
        group.set_margin_top(8)

        self._rows_shown = [
            "What's new",
            "Keyboard shortcuts",
            "Report an issue",
            "Credits and legal",
        ]
        group.add(
            _action(
                "What's new",
                "starred-symbolic",
                self._release_notes,
                suffix=Gtk.Image.new_from_icon_name("go-next-symbolic"),
            )
        )
        keys = Gtk.Label(label="Ctrl+/")
        keys.add_css_class("tf-small")
        keys.add_css_class("tf-faint")
        group.add(
            _action(
                "Keyboard shortcuts",
                "preferences-desktop-keyboard-symbolic",
                self._shortcuts,
                suffix=keys,
            )
        )
        group.add(
            _action(
                "Report an issue",
                "dialog-warning-symbolic",
                self._report,
                suffix=Gtk.Image.new_from_icon_name("external-link-symbolic"),
            )
        )
        group.add(
            _action(
                "Credits and legal",
                "text-x-generic-symbolic",
                self._credits,
                suffix=Gtk.Image.new_from_icon_name("go-next-symbolic"),
            )
        )
        return group

    def _premise(self) -> Gtk.Widget:
        label = Gtk.Label(label=PREMISE, wrap=True, justify=Gtk.Justification.CENTER)
        label.add_css_class("tf-micro")
        label.add_css_class("tf-faint")
        label.set_margin_top(12)
        label.set_margin_bottom(14)
        label.set_margin_start(20)
        label.set_margin_end(20)
        return label

    def _release_notes(self) -> None:
        if self._on_release_notes is not None:
            self._on_release_notes()

    def _shortcuts(self) -> None:
        self.close()
        if self._on_shortcuts is not None:
            self._on_shortcuts()

    def _report(self) -> None:
        """Opens the tracker with the two facts every report needs prefilled."""
        body = GLib.Uri.escape_string(
            f"Backsight {self._version}\nTerraform {self._engine or NOT_FOUND}\n\n", None, True
        )
        _launch(f"{ISSUES}?body={body}")

    def _credits(self) -> None:
        """The stock dialog, kept for exactly this.

        Built here rather than at start-up: its licence and credits handling is
        worth having, and none of it is needed until somebody asks.
        """
        stock = Adw.AboutDialog(
            application_name="Backsight",
            application_icon="com.kingletas.Backsight",
            version=self._version,
            developer_name="Luis Tineo",
            license_type=Gtk.License.MIT_X11,
            comments=DESCRIPTION,
        )
        stock.present(self)


def _action(title: str, icon: str, run: Callable[[], None], *, suffix: Gtk.Widget) -> Adw.ActionRow:
    row = Adw.ActionRow(title=title, activatable=True)
    row.add_prefix(Gtk.Image.new_from_icon_name(icon))
    row.add_suffix(suffix)
    row.connect("activated", lambda *_: run())
    return row


def _launch(uri: str) -> None:
    """Hands a link to the desktop, and says nothing when it will not take it."""
    try:
        Gio.AppInfo.launch_default_for_uri(uri, None)
    except GLib.Error:
        pass
