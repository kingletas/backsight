"""The library on screen: search, choose, and what happens when you use it."""

from __future__ import annotations

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.library_panel import NOTHING_MATCHED, NOTHING_YET, LibraryPanel  # noqa: E402
from backsight.engine.library.entry import Entry, Kind, Source, Step  # noqa: E402
from backsight.engine.library.store import Library  # noqa: E402


def an_entry(name: str, **rest) -> Entry:
    rest.setdefault("body", 'resource "aws_s3_bucket" "${1:name}" {}\n')
    return Entry(name=name, **rest)


def a_library() -> Library:
    """Distinct bodies, because search reaches into them on purpose — somebody
    looking for the bucket entry may only remember `force_destroy`."""
    return Library(
        entries=[
            an_entry(
                "Private bucket",
                tags=("s3",),
                resource="aws_s3_bucket",
                about="A bucket.",
                body='resource "aws_s3_bucket" "${1:name}" {\n  force_destroy = false\n}\n',
            ),
            an_entry(
                "Bucket policy",
                tags=("s3", "iam"),
                body='resource "aws_s3_bucket_policy" "${1:name}" {}\n',
            ),
            an_entry(
                "Rotate a password",
                kind=Kind.RUNBOOK,
                body="",
                steps=(Step(title="Snapshot", command="tofu apply -target=x"),),
            ),
            an_entry(
                "A whole module",
                kind=Kind.EXAMPLE,
                body='module "vpc" {\n  source = "./vpc"\n}\n',
            ),
        ]
    )


def test_an_empty_library_says_how_to_fill_it():
    panel = LibraryPanel()
    assert panel.said == NOTHING_YET
    assert "Save to library" in panel.said


def test_it_lists_what_it_has():
    panel = LibraryPanel()
    panel.show(a_library())
    assert len(panel.showing) == 4


def test_searching_narrows_it():
    panel = LibraryPanel()
    panel.show(a_library())
    panel.look_for("bucket")
    assert [entry.name for entry in panel.showing] == ["Bucket policy", "Private bucket"]


def test_the_body_is_searched_too_and_the_name_still_wins():
    """Somebody may only remember an argument they used, and a name that
    starts with what they typed is still what they meant."""
    panel = LibraryPanel()
    panel.show(a_library())
    panel.look_for("force_destroy")
    assert [entry.name for entry in panel.showing] == ["Private bucket"]


def test_a_term_that_matches_nothing_says_so_rather_than_looking_empty():
    panel = LibraryPanel()
    panel.show(a_library())
    panel.look_for("kubernetes")
    assert panel.said == NOTHING_MATCHED


def test_return_in_the_search_box_uses_the_best_match_without_a_click():
    """The complaint is typing the same block again. A click is one more thing."""
    used = []
    panel = LibraryPanel(on_insert=used.append)
    panel.show(a_library())
    panel.look_for("bucket")
    panel.search.emit("activate")
    assert [entry.name for entry in used] == ["Bucket policy"]


def test_an_example_is_opened_rather_than_inserted():
    """They are not all "insert" — an example is a file."""
    inserted, opened = [], []
    panel = LibraryPanel(on_insert=inserted.append, on_open=opened.append)
    panel.show(a_library())
    panel.look_for("whole module")
    panel.search.emit("activate")
    assert inserted == []
    assert [entry.name for entry in opened] == ["A whole module"]


def test_a_runbook_is_opened_too():
    opened = []
    panel = LibraryPanel(on_open=opened.append)
    panel.show(a_library())
    panel.look_for("rotate")
    panel.search.emit("activate")
    assert [entry.name for entry in opened] == ["Rotate a password"]


def test_the_button_says_what_it_will_do():
    panel = LibraryPanel()
    panel.show(a_library())
    panel.look_for("whole module")
    panel._choose(panel.showing[0])
    assert panel._use_it.get_label() == "Open as a new file"


def test_a_generated_entry_cannot_be_edited():
    panel = LibraryPanel()
    panel.show(Library(entries=[an_entry("Generated", source=Source.BUILT_IN)]))
    panel._choose(panel.showing[0])
    assert not panel._edit.get_visible()


def test_your_own_can_be():
    panel = LibraryPanel()
    panel.show(Library(entries=[an_entry("Mine", source=Source.YOURS)]))
    panel._choose(panel.showing[0])
    assert panel._edit.get_visible()


def test_the_preview_shows_what_will_actually_be_inserted():
    panel = LibraryPanel()
    panel.show(a_library())
    panel.look_for("Private bucket")
    panel._choose(panel.showing[0])
    assert "${1:" not in panel._preview.get_text()
    assert '"name"' in panel._preview.get_text()


def test_a_runbook_shows_its_steps_and_a_snippet_does_not():
    panel = LibraryPanel()
    panel.show(a_library())
    panel.look_for("rotate")
    panel._choose(panel.showing[0])
    assert panel._steps.get_visible()
    panel.look_for("bucket")
    panel._choose(panel.showing[0])
    assert not panel._steps.get_visible()


# --- what the schema adds --------------------------------------------------


def test_nothing_is_generated_until_somebody_types():
    """A list of every resource type in AWS is a directory listing."""
    asked = []
    panel = LibraryPanel()
    panel.show(Library())
    panel.ask_the_schema(lambda term: asked.append(term) or [])
    assert asked == []
    panel.look_for("aw")
    assert asked == []
    panel.look_for("aws")
    assert asked == ["aws"]


def test_a_generated_entry_appears_beside_the_written_ones():
    panel = LibraryPanel()
    panel.show(a_library())
    panel.ask_the_schema(
        lambda term: [an_entry("aws_s3_bucket — required only", source=Source.BUILT_IN)]
    )
    panel.look_for("bucket")
    assert "aws_s3_bucket — required only" in [entry.name for entry in panel.showing]


def test_a_written_entry_hides_the_generated_one_of_the_same_name():
    panel = LibraryPanel()
    panel.show(Library(entries=[an_entry("aws_s3_bucket — required only", source=Source.YOURS)]))
    panel.ask_the_schema(
        lambda term: [an_entry("aws_s3_bucket — required only", source=Source.BUILT_IN)]
    )
    panel.look_for("aws_s3")
    assert len(panel.showing) == 1
    assert panel.showing[0].source is Source.YOURS
