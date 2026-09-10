"""The About dialog answers the first three questions on any bug report."""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.about import DESCRIPTION, NOT_FOUND, PREMISE, AboutDialog  # noqa: E402


def test_it_says_what_backsight_is():
    """The stock dialog said nowhere what the product does."""
    assert DESCRIPTION in AboutDialog(version="0.1.0").says


def test_the_premise_is_there_because_it_is_the_reason_to_prefer_this():
    assert PREMISE in AboutDialog(version="0.1.0").says


def test_the_three_build_facts_are_all_shown():
    """Which build, which Terraform, and whether that pair is supported."""
    facts = AboutDialog(version="0.1.0", commit="8f2a41c", engine="1.9.8").facts
    assert facts["Version"] == "0.1.0 · 8f2a41c"
    assert facts["Terraform"] == "1.9.8 detected"
    assert facts["Tested against"]


def test_a_missing_terraform_is_stated_rather_than_hidden():
    """The absence is the useful information."""
    facts = AboutDialog(version="0.1.0", engine="").facts
    assert facts["Terraform"] == NOT_FOUND


def test_the_dialog_still_opens_with_no_terraform_on_path():
    """It must not need the engine to be there in order to say it is not."""
    assert AboutDialog(version="0.1.0", engine="").facts["Terraform"] == NOT_FOUND


def test_a_build_with_no_commit_shows_the_version_alone():
    """An installed build has no repository, and a wrong commit is worse."""
    assert AboutDialog(version="0.1.0", commit="").facts["Version"] == "0.1.0"


def test_every_action_row_is_there():
    assert AboutDialog(version="0.1.0").rows == [
        "What's new",
        "Keyboard shortcuts",
        "Report an issue",
        "Credits and legal",
    ]


def test_the_shortcuts_row_closes_and_hands_over():
    asked: list[str] = []
    dialog = AboutDialog(version="0.1.0", on_shortcuts=lambda: asked.append("shortcuts"))
    dialog._shortcuts()
    assert asked == ["shortcuts"]


def test_the_icon_is_the_application_and_not_the_document_fallback():
    """A generic glyph reads as unfinished software."""
    from gi.repository import Gdk, Gtk

    dialog = AboutDialog(version="0.1.0")
    assert dialog.icon_name == "com.kingletas.Backsight"
    assert "text-x-generic" not in dialog.icon_name

    # Building a window is enough: the theme registers the search path, so an
    # application is not needed for the mark to resolve. It used to be, and the
    # smoke drew the broken-image glyph because of it.
    from backsight.app.theme import Theme

    Theme()
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    assert theme.has_icon(dialog.icon_name), "the icon is named but does not resolve"
