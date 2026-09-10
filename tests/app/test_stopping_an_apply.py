"""The apply screen offers a way to intervene, and the engine decides when.

**The one screen where something irreversible is happening offered `Close` and
nothing else.** Somebody watching the wrong thing being destroyed had to leave
the screen and find a menu.
"""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.apply_screen import ApplyScreen  # noqa: E402
from backsight.engine.plan.applying import Progress, Stage, Step  # noqa: E402
from backsight.engine.plan.view import Action  # noqa: E402


def _running() -> Progress:
    return Progress(
        steps=[
            Step("aws_s3_bucket.one", Action.CREATE, Stage.DONE, seconds=4.0),
            Step("aws_sqs_queue.two", Action.DELETE, Stage.RUNNING),
            Step("aws_dynamodb_table.three", Action.CREATE),
        ]
    )


def test_the_control_says_what_it_does():
    asked = []
    screen = ApplyScreen(on_stop=lambda: asked.append(True))
    screen.begin(_running())
    assert screen._stop.get_visible()
    assert screen._stop.get_label() == "Stop after this resource"


def test_pressing_it_asks_once_and_says_it_is_asking():
    asked = []
    screen = ApplyScreen(on_stop=lambda: asked.append(True))
    screen.begin(_running())
    screen._stop.emit("clicked")
    assert asked == [True]
    assert not screen._stop.get_sensitive()
    assert "Stopping" in screen._stop.get_label()


def test_it_is_gone_once_the_apply_is_over():
    screen = ApplyScreen(on_stop=lambda: None)
    progress = _running()
    screen.begin(progress)
    progress.finished = True
    screen.finished(progress)
    assert not screen._stop.get_visible()
    assert screen._close.get_visible()


def test_there_is_no_stop_control_when_nothing_can_be_stopped():
    screen = ApplyScreen()
    screen.begin(_running())
    assert not screen._stop.get_visible()


def test_each_resource_carries_its_own_elapsed_time():
    screen = ApplyScreen()
    screen.begin(_running())
    took = [screen._rows[address][2].get_text() for address in screen._rows]
    assert took[0] == "4s"
    # Running and waiting show nothing: there is no finished time to give.
    assert took[1] == ""
    assert took[2] == ""


def test_finishing_in_under_a_second_is_not_drawn_as_never_starting():
    """A real capture of `terraform_data` completes in 0s, and a blank there
    read exactly like the resource that was never reached."""
    screen = ApplyScreen()
    screen.begin(
        Progress(
            steps=[
                Step("terraform_data.quick", Action.CREATE, Stage.DONE, seconds=0.0),
                Step("terraform_data.skipped", Action.CREATE, Stage.NEVER_REACHED),
            ]
        )
    )
    took = [screen._rows[address][2].get_text() for address in screen._rows]
    assert took == ["<1s", ""]


# --- consequence outlives the apply ---------------------------------------


def _applied() -> Progress:
    return Progress(
        steps=[
            Step("aws_s3_bucket.made", Action.CREATE, Stage.DONE, seconds=2.0),
            Step("aws_sqs_queue.gone", Action.DELETE, Stage.DONE, seconds=1.0),
            Step("aws_dynamodb_table.moved", Action.UPDATE, Stage.DONE, seconds=3.0),
        ],
        finished=True,
    )


def _tone(screen, address: str) -> str:
    label = screen._rows[address][1]
    for one in ("tf-safe", "tf-disruptive", "tf-irreversible", "tf-faint"):
        if label.has_css_class(one):
            return one
    return ""


def test_a_destroy_that_succeeded_is_not_drawn_as_a_create():
    """Four outcomes in one green made the row somebody is looking for the
    hardest one to find."""
    screen = ApplyScreen()
    screen.begin(_applied())
    assert _tone(screen, "aws_s3_bucket.made") == "tf-safe"
    assert _tone(screen, "aws_sqs_queue.gone") == "tf-irreversible"
    assert _tone(screen, "aws_dynamodb_table.moved") == "tf-disruptive"


def test_a_failure_is_still_told_apart_from_a_successful_destroy():
    """By shape, which is what the icon is for — the colour is the same."""
    from backsight.app.apply_screen import ICONS

    assert ICONS[Stage.FAILED] != ICONS[Stage.DONE]
