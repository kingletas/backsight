"""Auto-closing, against a real buffer rather than only the decision."""

from __future__ import annotations

import shutil
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib  # noqa: E402

from backsight.app.editor import Page  # noqa: E402

Adw.init()

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "plannable" / "main.tf"


class Fixed:
    """Settings with one answer, so a test says what it is testing."""

    def __init__(self, **values):
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def settle() -> None:
    """Closing happens on idle, because the buffer is mid-insert until then."""
    context = GLib.MainContext.default()
    for _ in range(50):
        context.iteration(False)


def a_page(tmp_path: Path, **settings) -> Page:
    where = tmp_path / "main.tf"
    shutil.copy(FIXTURE, where)
    page = Page(where, settings=Fixed(**settings))
    page.buffer.set_text("")
    return page


def typed(page: Page, text: str) -> None:
    for character in text:
        page.buffer.insert_at_cursor(character)
        settle()


def test_a_bracket_closes_itself(tmp_path: Path):
    page = a_page(tmp_path)
    typed(page, "max(")
    assert page.text() == "max()"


def test_and_the_caret_lands_between_them(tmp_path: Path):
    page = a_page(tmp_path)
    typed(page, "max(")
    typed(page, "1")
    assert page.text() == "max(1)"


def test_typing_the_closer_does_not_leave_two(tmp_path: Path):
    page = a_page(tmp_path)
    typed(page, "max(1)")
    assert page.text() == "max(1)"


def test_a_quote_closes_itself(tmp_path: Path):
    page = a_page(tmp_path)
    typed(page, 'input = "')
    assert page.text() == 'input = ""'


def test_finishing_a_string_does_not_open_another(tmp_path: Path):
    page = a_page(tmp_path)
    typed(page, 'input = "one"')
    assert page.text() == 'input = "one"'


def test_a_bracket_before_a_word_is_left_alone(tmp_path: Path):
    """Typing `(` before a token almost always means wrapping it."""
    page = a_page(tmp_path)
    page.buffer.set_text("var.name")
    page.buffer.place_cursor(page.buffer.get_start_iter())
    typed(page, "(")
    assert page.text() == "(var.name"


def test_it_can_be_turned_off(tmp_path: Path):
    page = a_page(tmp_path, **{"editor.close_brackets": False})
    typed(page, "max(")
    assert page.text() == "max("


def test_pasted_text_is_never_bracketed(tmp_path: Path):
    """A paste, a snippet and a format all arrive the same way as typing."""
    page = a_page(tmp_path)
    page.buffer.insert_at_cursor('input = "one" # (see above)')
    settle()
    assert page.text() == 'input = "one" # (see above)'
