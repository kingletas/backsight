"""A save is one step, so a reader never sees half a file."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from backsight.engine.hcl.document import Document


def test_the_content_arrives(tmp_path: Path):
    path = tmp_path / "main.tf"
    Document(path=path, data=b'resource "terraform_data" "a" {}\n').write()
    assert path.read_bytes() == b'resource "terraform_data" "a" {}\n'


def test_no_temporary_file_is_left_behind(tmp_path: Path):
    path = tmp_path / "main.tf"
    Document(path=path, data=b"one\n").write()
    Document(path=path, data=b"two\n").write()
    assert [entry.name for entry in tmp_path.iterdir()] == ["main.tf"]


def test_an_existing_file_keeps_its_permissions(tmp_path: Path):
    """They may have been set deliberately, and a save is not the place to change them."""
    path = tmp_path / "main.tf"
    path.write_bytes(b"old\n")
    os.chmod(path, 0o640)
    Document(path=path, data=b"new\n").write()
    assert path.stat().st_mode & 0o777 == 0o640


def test_a_reader_never_sees_a_partial_file(tmp_path: Path):
    """The defect this replaces: a truncate-then-fill leaves an empty window.

    Everything in this application reads these files while they are edited, and
    a reader landing in that window reports a workspace with no resources.
    """
    path = tmp_path / "main.tf"
    original = b'resource "terraform_data" "a" {}\n'
    path.write_bytes(original)
    replacement = b'resource "terraform_data" "b" {}\n' * 400

    seen: list[bytes] = []
    stop = threading.Event()

    def read() -> None:
        while not stop.is_set():
            try:
                seen.append(path.read_bytes())
            except FileNotFoundError:
                seen.append(b"")

    watcher = threading.Thread(target=read, daemon=True)
    watcher.start()
    for _ in range(50):
        Document(path=path, data=replacement).write()
        Document(path=path, data=original).write()
    stop.set()
    watcher.join(timeout=5)

    assert seen, "the reader never got a look in"
    assert set(seen) <= {original, replacement}, "a partial file was visible"


def test_writing_somewhere_else_leaves_the_original_alone(tmp_path: Path):
    source = tmp_path / "main.tf"
    source.write_bytes(b"original\n")
    Document(path=source, data=b"copied\n").write(tmp_path / "other.tf")
    assert source.read_bytes() == b"original\n"
    assert (tmp_path / "other.tf").read_bytes() == b"copied\n"


def test_reindenting_moves_the_block_and_keeps_its_shape():
    """A nested line stays nested; only the block moves."""
    from backsight.engine.text.lines import reindent

    block = 'resource "a" "b" {\n  input = 1\n  nested {\n    x = 2\n  }\n}'
    moved = reindent(block, "    ")
    lines = moved.split("\n")
    assert lines[0] == 'resource "a" "b" {'
    assert lines[1] == "      input = 1"
    assert lines[3] == "        x = 2"


def test_the_first_line_lands_where_the_caret_already_is():
    from backsight.engine.text.lines import reindent

    assert reindent("one\ntwo", "  ").split("\n")[0] == "one"


def test_a_blank_line_stays_blank_rather_than_gaining_whitespace():
    """Trailing whitespace on an empty line is a diff nobody asked for."""
    from backsight.engine.text.lines import reindent

    assert reindent("one\n\ntwo", "  ").split("\n")[1] == ""


def test_reindenting_something_already_flat_adds_the_indent():
    from backsight.engine.text.lines import reindent

    assert reindent("one\ntwo", "\t").split("\n")[1] == "\ttwo"


def test_reindenting_nothing_is_nothing():
    from backsight.engine.text.lines import reindent

    assert reindent("", "  ") == ""
    assert reindent("\n\n", "  ") == "\n\n"


def test_the_indentation_of_a_line_is_read_exactly_as_written():
    from backsight.engine.text.lines import indentation_of

    assert indentation_of("\t  x") == "\t  "
    assert indentation_of("x") == ""
