"""Looking at a hidden panel without the layout arguing about it."""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.window import Window  # noqa: E402
from backsight.engine.layout.panels import Visibility  # noqa: E402


@pytest.fixture
def window():
    found = Window()
    found.hide_panel("left_rail")
    return found


def test_peeking_shows_it_without_changing_the_saved_layout(window):
    """Pressing a key to check one thing and having to press it again to put
    it back is the layout arguing with somebody who only wanted to look."""
    window.peek("left_rail")
    assert window._sidebar_widget.get_visible()
    assert window.layout.visibility("left_rail") is Visibility.HIDDEN


def test_escape_puts_it_back(window):
    window.peek("left_rail")
    assert window.stop_peeking()
    assert not window._sidebar_widget.get_visible()
    assert window.layout.visibility("left_rail") is Visibility.HIDDEN


def test_escape_with_nothing_peeked_does_nothing(window):
    assert not window.stop_peeking()


def test_pinning_what_you_are_looking_at_keeps_it(window):
    window.peek("left_rail")
    window.keep_peeked()
    assert window.layout.visibility("left_rail") is Visibility.SHOWN
    assert not window.stop_peeking()


def test_peeking_at_something_already_showing_just_toggles_it(window):
    window.show_panel("left_rail")
    window.peek("left_rail")
    assert window.layout.visibility("left_rail") is not Visibility.SHOWN


def test_a_peeked_rail_shows_the_rail_rather_than_the_strip(window):
    window.peek("left_rail")
    assert window._rail_scroller.get_visible()
    assert not window._rail_strip.get_visible()


def test_escape_ends_a_peek_before_anything_else_it_might_do(window):
    """Pressed, not called: the handler is reached through the controller chain."""
    from tests.pressing import press_escape

    window.peek("left_rail")
    press_escape(window)
    assert not window._sidebar_widget.get_visible()


# --- the rehearsal ---------------------------------------------------------


def test_a_container_runtime_is_looked_for_rather_than_assumed_absent():
    """It was hardcoded False, so the rail said a rehearsal was unavailable on
    a machine that had Docker installed the whole time."""
    from backsight.engine.sandbox.runtime import detect

    window = Window()
    assert window._container_runtime == (detect() is not None)


def test_a_rehearsal_with_no_runtime_says_so_when_asked_and_not_when_not():
    window = Window()
    window._container_runtime = False
    said = []
    window._still_true = said.append
    window.run_convergence(asked=False)
    assert said == []
    window.run_convergence()
    assert len(said) == 1
    assert "Docker or Podman" in said[0]


def test_it_never_calls_a_rehearsal_a_prediction():
    """A sandbox result is whether the configuration applies cleanly, not
    whether the cloud will behave the same way."""
    import inspect

    said = inspect.getdoc(Window.run_convergence).lower()
    assert "rehearsal" in said
    assert "never a prediction" in said
