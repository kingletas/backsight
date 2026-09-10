"""A thing that is still true goes in the banner, never in a toast forever.

Three messages were toasts with `timeout=0` — a workspace that is not
initialised, a file changed on disk under an unsaved buffer, and unsaved work
found at launch. A toast that never leaves is a banner wearing a toast's
clothes: it sits over the window in the corner with no way to tell it from the
four-second one that was there a moment ago.
"""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.window import Window  # noqa: E402


@pytest.fixture
def window():
    return Window()


def test_no_toast_is_asked_to_last_forever():
    """A zero timeout in libadwaita means never. Parsed rather than grepped, so
    a comment explaining the rule does not trip it."""
    import ast

    app = Path("src/backsight/app")
    forever = []
    for path in app.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg != "timeout":
                    continue
                if isinstance(keyword.value, ast.Constant) and keyword.value.value == 0:
                    forever.append(f"{path.name}:{node.lineno}")
    assert forever == [], "toasts that never leave: " + ", ".join(forever)


def blocked(tmp_path):
    """A workspace with no `.terraform` and no backend — the ordinary state of
    one somebody has just cloned."""
    (tmp_path / "main.tf").write_text('resource "terraform_data" "a" {}\n', encoding="utf-8")
    found = Window()
    found.open_workspace(tmp_path)
    found.open_file(tmp_path / "main.tf")
    found.show_what_is_blocking()
    return found


def test_nothing_is_blocking_before_a_workspace_is_open(window):
    window.show_what_is_blocking()
    assert not window._banner.get_revealed()


def test_the_banner_names_one_condition_and_what_clears_it(tmp_path):
    found = blocked(tmp_path)
    assert found._banner.get_revealed()
    assert found._blocking is not None
    assert found._banner.get_button_label()
    # What is wrong, what it prevents, and roughly how long the fix takes.
    assert found._blocking.title in found._banner.get_title()
    assert found._blocking.body in found._banner.get_title()


def test_a_blocking_banner_cannot_be_dismissed_away(tmp_path):
    """Dismissing "this workspace has not been initialised" would hide the
    reason nothing works."""
    found = blocked(tmp_path)
    assert not found._blocking.dismissible
    found.dismiss_banner()
    assert found._banner.get_revealed()


def test_a_message_with_nothing_to_do_just_dismisses(window):
    window._still_true("latin1.tf cannot be read — not UTF-8")
    assert window._banner.get_button_label() == "Dismiss"
    window._banner_clicked()
    assert not window._banner.get_revealed()


def test_the_action_does_not_survive_the_next_message(window):
    """Otherwise Dismiss on an unrelated banner runs the last one's action."""
    done = []
    window._still_true("first", action="Do it", then=lambda: done.append("ran"))
    window._still_true("second")
    window._banner_clicked()
    assert done == []


def test_several_files_changing_underneath_ask_once(window, tmp_path):
    """They arrive together — a branch switch touches several — and a stack of
    permanent notices is a stack nobody reads."""
    from backsight.app import window as module

    pages = [type("P", (), {"path": tmp_path / f"{name}.tf"})() for name in ("a", "b")]
    said = module._changed_underneath(pages)
    assert "a.tf, b.tf" in said
    assert "unsaved changes" in said


def test_too_many_to_name_are_counted_instead(window, tmp_path):
    pages = [type("P", (), {"path": tmp_path / f"{n}.tf"})() for n in "abcde"]
    assert "5 open files" in __import__("backsight.app.window", fromlist=["x"])._changed_underneath(
        pages
    )
