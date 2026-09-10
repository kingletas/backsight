"""A file opened in the editor and saved without editing is unchanged.

FR-ED-07 and DD-9, over the corpus that exists to break it: mixed tabs, CRLF, a
byte order mark, a missing trailing newline, heredocs and an empty file. Six of
these are files `tofu fmt` would rewrite, and rewriting them is the defect.

These need the toolkit but not a display: a buffer draws nothing.
"""

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("GtkSource", "5")

from backsight.app.editor import Page  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CORPUS = sorted((ROOT / "fixtures" / "hcl" / "ugly").glob("*.tf"))


def test_the_corpus_is_present():
    assert len(CORPUS) >= 20


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_open_and_save_without_editing_is_byte_identical(path: Path, tmp_path: Path):
    copied = tmp_path / path.name
    copied.write_bytes(path.read_bytes())
    page = Page(copied)
    page.save()
    assert copied.read_bytes() == path.read_bytes()


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_the_buffer_holds_what_the_file_holds(path: Path):
    """A file that survives saving because the bytes were kept could still be
    displayed wrongly. This checks what is shown, not only what is written."""
    page = Page(path)
    shown = page.buffer.get_text(page.buffer.get_start_iter(), page.buffer.get_end_iter(), True)
    # Decoded from bytes rather than `read_text`, which turns CRLF into LF on the
    # way in. That is the same silent normalisation this feature forbids, and
    # reading the file that way would hide the buffer having kept it.
    assert shown == path.read_bytes().decode("utf-8")


def test_loading_a_file_is_not_undoable(tmp_path: Path):
    """An undo that empties a file nobody edited is data loss, not an undo."""
    path = tmp_path / "main.tf"
    path.write_text('resource "null_resource" "a" {}\n')
    page = Page(path)
    assert page.buffer.get_can_undo() is False
    page.buffer.undo()
    shown = page.buffer.get_text(page.buffer.get_start_iter(), page.buffer.get_end_iter(), True)
    assert shown == 'resource "null_resource" "a" {}\n'


def test_an_edit_can_be_undone(tmp_path: Path):
    path = tmp_path / "main.tf"
    path.write_text("one\n")
    page = Page(path)
    page.buffer.insert_at_cursor("two")
    assert page.buffer.get_can_undo() is True
    page.buffer.undo()
    assert page.content() == b"one\n"


def test_a_file_is_only_marked_modified_once_it_is_edited(tmp_path: Path):
    path = tmp_path / "main.tf"
    path.write_text("one\n")
    page = Page(path)
    assert page.modified is False
    page.buffer.insert_at_cursor("two")
    assert page.modified is True
    page.save()
    assert page.modified is False


def test_an_edited_file_is_written_with_the_edit_and_nothing_else(tmp_path: Path):
    """Saving an edit must not tidy the rest of the file on the way past."""
    path = tmp_path / "ugly.tf"
    original = b'resource "a" "b" {\n\tx=1\n   y  =  2\n}\n'
    path.write_bytes(original)
    page = Page(path)
    page.buffer.insert(page.buffer.get_end_iter(), '\nresource "c" "d" {}\n')
    page.save()
    assert path.read_bytes() == original + b'\nresource "c" "d" {}\n'


def test_the_language_is_recognised():
    """If the bundled Terraform definition disappears, highlighting goes silently."""
    page = Page(CORPUS[0])
    language = page.buffer.get_language()
    assert language is not None and language.get_id() == "terraform"


def test_an_unmodified_page_writes_the_bytes_it_read_and_not_a_re_encoding():
    """The guarantee itself, rather than its effect.

    Every file in the corpus happens to survive a decode and an encode, so
    dropping this shortcut breaks none of the tests above. The shortcut is what
    makes the round trip guaranteed instead of lucky, so it is asserted directly.
    """
    page = Page(CORPUS[0])
    assert page.content() is page.document.data


def test_a_file_that_is_not_utf8_is_refused_by_name(tmp_path: Path):
    """Showing it is impossible: a reversible decode makes surrogates the buffer
    will not hold, and a lossy one saves different bytes than it opened."""
    from backsight.engine.hcl.document import NotUtf8

    path = ROOT / "fixtures" / "hcl" / "not-utf8" / "latin1.tf"
    with pytest.raises(NotUtf8) as raised:
        Page(path)
    assert "not UTF-8" in str(raised.value)
    assert raised.value.position == 34
    # And it is left exactly as it was found.
    assert path.read_bytes().count(b"\xe9") == 1


def test_two_files_with_the_same_name_are_told_apart_in_their_tabs(tmp_path: Path):
    """Every Terraform module has a main.tf. Three tabs reading `main.tf` is
    the ordinary case, not the unlucky one."""
    from backsight.app.editor import Editor

    first = tmp_path / "prod"
    second = tmp_path / "staging"
    for directory in (first, second):
        directory.mkdir()
        (directory / "main.tf").write_text('resource "null_resource" "a" {}\n')

    editor = Editor()
    editor.open(first / "main.tf")
    assert editor._name_for(editor.pages[(first / "main.tf").resolve()]) == "main.tf"
    editor.open(second / "main.tf")
    assert editor._name_for(editor.pages[(first / "main.tf").resolve()]) == "prod/main.tf"
    assert editor._name_for(editor.pages[(second / "main.tf").resolve()]) == "staging/main.tf"


def test_two_annotations_on_one_line_become_one():
    """A verdict and a code lens both belong to the line a resource starts on,
    and drawn on top of each other they read as one garbled string."""
    from backsight.app.annotation_lane import Annotation, merge

    merged = merge(
        [
            Annotation(line=4, text="Add", tone="add"),
            Annotation(line=4, text="no references · added in plan", tone="hint"),
            Annotation(line=9, text="Replace", tone="destroy"),
        ]
    )
    assert [item.line for item in merged] == [4, 9]
    assert merged[0].text == "Add · no references · added in plan"


def test_the_more_consequential_tone_decides_how_a_merged_row_looks():
    from backsight.app.annotation_lane import Annotation, merge

    merged = merge(
        [
            Annotation(line=2, text="hint", tone="hint"),
            Annotation(line=2, text="gone", tone="destroy"),
        ]
    )
    assert merged[0].tone == "destroy"


def test_a_single_annotation_is_left_exactly_as_it_was():
    from backsight.app.annotation_lane import Annotation, merge

    only = Annotation(line=7, text="Add", tone="add")
    assert merge([only]) == [only]


def test_merging_keeps_the_lines_in_order():
    from backsight.app.annotation_lane import Annotation, merge

    merged = merge(
        [Annotation(line=9, text="b", tone="add"), Annotation(line=2, text="a", tone="add")]
    )
    assert [item.line for item in merged] == [2, 9]


def test_only_the_worst_explanation_on_a_screenful_is_drawn():
    """A wall of permanent annotations is unreadable, and what people do about
    an unreadable wall is read none of it."""
    from backsight.app.annotation_lane import Annotation, visible_on

    said = [
        Annotation(line=3, text="Add", tone="add"),
        Annotation(line=8, text="Destroy", tone="destroy"),
        Annotation(line=12, text="Change", tone="change"),
    ]
    kept = visible_on(said, first=1, last=40, caret=1)
    assert [item.text for item in kept] == ["Destroy"]


def test_the_caret_line_keeps_its_own_explanation_as_well():
    from backsight.app.annotation_lane import Annotation, visible_on

    said = [
        Annotation(line=3, text="Add", tone="add"),
        Annotation(line=8, text="Destroy", tone="destroy"),
    ]
    kept = visible_on(said, first=1, last=40, caret=3)
    assert [item.line for item in kept] == [3, 8]


def test_every_lens_in_view_is_drawn_because_a_setting_asked_for_it():
    from backsight.app.annotation_lane import Annotation, visible_on

    said = [
        Annotation(line=2, text="3 references", tone="hint", kind="lens"),
        Annotation(line=9, text="1 reference", tone="hint", kind="lens"),
    ]
    assert len(visible_on(said, first=1, last=40, caret=None)) == 2


def test_a_resolved_value_is_only_on_the_line_the_caret_is_on():
    from backsight.app.annotation_lane import Annotation, visible_on

    said = [
        Annotation(line=4, text="= 10.0.1.0/24", tone="hint", kind="hint"),
        Annotation(line=11, text="= t3.small", tone="hint", kind="hint"),
    ]
    assert [item.line for item in visible_on(said, first=1, last=40, caret=4)] == [4]


def test_nothing_off_the_screenful_is_drawn_at_all():
    from backsight.app.annotation_lane import Annotation, visible_on

    said = [Annotation(line=200, text="Destroy", tone="destroy")]
    assert visible_on(said, first=1, last=40, caret=None) == []
