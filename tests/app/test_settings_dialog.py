"""Preferences shows which layer supplied the value in effect."""

import pytest

from backsight.app.settings_dialog import (
    CHOICES,
    ELSEWHERE,
    GROUPS,
    TITLES,
    WORDS,
    description_of,
    provenance,
    shown,
    title_of,
    warnings_for,
)
from backsight.engine.settings.layers import DEFAULTS, Settings
from backsight.engine.settings.layers import load as load

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from backsight.app.settings_dialog import SettingsDialog  # noqa: E402


def test_a_file_the_person_did_not_open_is_named():
    """The one case where a switch is moved and nothing happens."""
    settings = Settings(
        layers={"default": {"editor.tab_size": 4}, "workspace": {"editor.tab_size": 8}}
    )
    assert provenance(settings, "editor.tab_size") == ELSEWHERE["workspace"]
    assert ".backsight/settings.toml" in provenance(settings, "editor.tab_size")


def test_the_defaults_winning_is_not_worth_saying():
    """Every row carrying `default: tofu  ← in effect` is our storage model,
    printed thirty-eight times into somebody else's window."""
    assert provenance(Settings(), "terraform.binary") == ""


def test_the_person_own_choice_winning_is_not_worth_saying_either():
    settings = Settings(layers={"user": {"terraform.plan_on_save": False}})
    assert provenance(settings, "terraform.plan_on_save") == ""


def test_a_value_reads_as_a_phrase_rather_than_as_the_token_we_store():
    assert shown("files.open_on", "single_click") == "A single click"
    assert shown("tabs.new_tab_position", "after_current") == "Next to the current tab"
    assert shown("appearance.color_scheme", "follow_system") == "Follow the desktop"


def test_booleans_read_as_on_and_off_rather_than_true_and_false():
    assert shown("terraform.plan_on_save", True) == "On"
    assert shown("terraform.plan_on_save", False) == "Off"


def test_a_value_nobody_wrote_a_word_for_is_shown_as_it_is():
    """An editor scheme somebody installed themselves has no phrase here."""
    assert shown("appearance.editor_scheme_light", "solarized") == "solarized"


def test_no_setting_is_titled_by_stripping_its_key():
    """`files.open_on` became "Open on", which asks a question rather than
    answering one."""
    for _title, _icon, _description, keys in GROUPS:
        for key in keys:
            assert key in TITLES, key
            assert title_of(key) != key.rsplit(".", 1)[-1].replace("_", " ").capitalize()


def test_no_machine_word_reaches_a_title_or_a_description():
    for _title, _icon, _description, keys in GROUPS:
        for key in keys:
            said = f"{title_of(key)} {description_of(key)}"
            assert "_" not in said.replace("_ms", ""), key


def test_every_choice_has_a_word_for_every_one_of_its_values():
    for key, options in CHOICES.items():
        for option in options:
            assert option in WORDS, f"{key} offers {option} with nothing to call it"


def test_no_pairing_of_the_file_settings_warns():
    """A single click that opens keeps every file it opens, whatever the reuse
    setting says, so the pairing that used to warn no longer interacts."""
    for open_on in ("single_click", "double_click"):
        for reuse in (True, False):
            settings = Settings(
                layers={"user": {"files.open_on": open_on, "files.preview_tabs": reuse}}
            )
            assert warnings_for(settings) == [], (open_on, reuse)


def test_a_retired_value_is_shown_as_what_it_now_does():
    """A double click always opens now, so *never* is gone. A file that still
    says it must not appear as the first option, which is the opposite."""
    from backsight.engine.settings.keys import Keymap

    settings = Settings(
        layers={"default": dict(DEFAULTS), "user": {"files.promote_preview_on": "never"}}
    )
    dialog = SettingsDialog(settings, keymap=Keymap.build())
    row = next(
        widget
        for widget in _widgets(dialog)
        if isinstance(widget, Adw.ComboRow) and widget.get_title() == "Keep a previewed file open"
    )
    assert row.get_selected_item().get_string() == "A double click"


def test_every_key_the_dialog_shows_is_a_key_that_exists():
    """A row for a setting nothing reads is a row that lies."""
    shown = {key for _title, _icon, _description, keys in GROUPS for key in keys}
    unknown = shown - set(DEFAULTS)
    assert not unknown, f"the dialog offers {sorted(unknown)}, which nothing reads"


def test_the_groups_cover_the_settings_worth_showing():
    shown = {key for _title, _icon, _description, keys in GROUPS for key in keys}
    # Layout is remembered rather than configured in the dialog. Everything
    # else should be reachable, editor settings included — the requirements ask
    # for an Editor section and there was none.
    expected = {k for k in DEFAULTS if not k.startswith("layout.")}
    assert expected <= shown, f"not offered anywhere: {sorted(expected - shown)}"


def test_every_page_carries_an_icon():
    """A preferences page without one draws a broken image, which the first
    screenshot showed as six red squares along the bottom."""
    for _title, icon, _description, _keys in GROUPS:
        assert icon.endswith("-symbolic")


def test_the_keys_page_lists_every_command():
    """Keys is a page of the dialog, and every binding on it can be changed."""
    from backsight.engine.settings.keys import DEFAULTS, Keymap

    dialog = SettingsDialog(load(), keymap=Keymap.build())
    shown = _titles(dialog)
    for command in DEFAULTS:
        assert command.label in shown


def test_a_command_that_cannot_be_unbound_says_so():
    from backsight.engine.settings.keys import THE_FLOOR, Keymap

    keymap = Keymap.build()
    dialog = SettingsDialog(load(), keymap=keymap)
    floor = [keymap.commands[action].label for action in THE_FLOOR]
    subtitles = _subtitles(dialog)
    for label in floor:
        assert any(label in title for title in _titles(dialog))
    assert "cannot be unbound" in subtitles


def test_a_conflict_is_reported_rather_than_resolved():
    """Choosing for someone silently loses a binding they meant to have."""
    from backsight.engine.settings.keys import Keymap

    keymap = Keymap.build({"plan": "<Control>s"})
    dialog = SettingsDialog(load(), keymap=keymap)
    assert any("<Control>s is bound to" in title for title in _titles(dialog))


def test_rebinding_reaches_the_caller():
    from backsight.engine.settings.keys import Keymap

    changed: list[tuple[str, str | None]] = []
    dialog = SettingsDialog(
        load(), keymap=Keymap.build(), on_rebind=lambda a, k: changed.append((a, k))
    )
    entry = next(w for w in _widgets(dialog) if isinstance(w, Gtk.Entry))
    entry.set_text("<Control>9")
    entry.emit("activate")
    assert changed and changed[0][1] == "<Control>9"


def _widgets(root):
    found = []
    stack = [root.get_content() if hasattr(root, "get_content") else root]
    while stack:
        widget = stack.pop()
        if widget is None:
            continue
        found.append(widget)
        child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
        while child is not None:
            stack.append(child)
            child = child.get_next_sibling()
    return found


def _titles(dialog) -> list[str]:
    return [w.get_title() for w in _widgets(dialog) if isinstance(w, Adw.PreferencesRow)]


def _subtitles(dialog) -> list[str]:
    return [w.get_subtitle() or "" for w in _widgets(dialog) if isinstance(w, Adw.ActionRow)]


def walk(widget):
    child = widget.get_first_child() if hasattr(widget, "get_first_child") else None
    while child is not None:
        yield child
        yield from walk(child)
        child = child.get_next_sibling()


def rows(dialog):
    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw as _Adw
    from gi.repository import Gtk as _Gtk

    kinds = (_Adw.SwitchRow, _Adw.ComboRow, _Adw.SpinRow, _Adw.EntryRow)
    found = [w for w in walk(dialog) if isinstance(w, kinds)]
    # A free-text setting is an action row with an entry in it, because an
    # `Adw.EntryRow` has no subtitle and everything the row had to say — the
    # font warning above all — went onto a tooltip.
    found += [
        w
        for w in walk(dialog)
        if isinstance(w, _Adw.ActionRow) and any(isinstance(c, _Gtk.Entry) for c in walk(w))
    ]
    return found


def test_every_setting_is_a_control_not_a_label():
    """A preferences window that cannot change a preference is a viewer."""
    from backsight.engine.settings.layers import load

    dialog = SettingsDialog(load())
    shown = {key for _t, _i, _d, keys in GROUPS for key in keys}
    assert len(rows(dialog)) >= len(shown)


def test_a_value_with_a_fixed_set_of_answers_is_never_free_text():
    """A box somebody can typo `follow_sistem` into is not a setting."""
    import gi

    gi.require_version("Adw", "1")
    from gi.repository import Adw as _Adw

    from backsight.app.settings_dialog import CHOICES
    from backsight.engine.settings.layers import DEFAULTS, load

    dialog = SettingsDialog(load())
    combos = [r for r in rows(dialog) if isinstance(r, _Adw.ComboRow)]
    assert len(combos) == len({k for k in CHOICES if k in DEFAULTS})


def test_every_choice_offered_is_a_value_the_setting_can_hold():
    from backsight.app.settings_dialog import CHOICES
    from backsight.engine.settings.layers import DEFAULTS

    for key, options in CHOICES.items():
        assert key in DEFAULTS, key
        assert DEFAULTS[key] in options, f"{key} defaults to {DEFAULTS[key]!r}, not offered"


def test_changing_one_writes_it_and_says_so(tmp_path, monkeypatch):
    from backsight.engine.settings import writing
    from backsight.engine.settings.layers import load

    monkeypatch.setattr(writing, "user_file", lambda home=None: tmp_path / "settings.toml")
    heard = []
    dialog = SettingsDialog(load(), on_change=lambda k, v: heard.append((k, v)))
    dialog._changed("editor.word_wrap", True)
    assert heard == [("editor.word_wrap", True)]
    assert "word_wrap = true" in (tmp_path / "settings.toml").read_text()


def test_a_write_that_fails_says_so_rather_than_looking_like_it_worked(tmp_path, monkeypatch):
    from backsight.engine.settings import writing
    from backsight.engine.settings.layers import load

    def refuse(*_a, **_k):
        raise OSError("read-only file system")

    monkeypatch.setattr(writing, "remember", refuse)
    heard = []
    dialog = SettingsDialog(load(), on_change=lambda k, v: heard.append((k, v)))
    dialog._changed("editor.word_wrap", True)
    assert heard == []
