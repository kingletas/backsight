"""What happens when a file changes outside the editor, and after a crash."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

from backsight.app.window import Window  # noqa: E402
from backsight.engine.workspace import recovery  # noqa: E402

Adw.init()

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "plannable"


def a_workspace(tmp_path: Path) -> Path:
    where = tmp_path / "workspace"
    shutil.copytree(FIXTURE, where)
    return where


def rewritten(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    later = os.stat(path).st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(later, later))


def test_an_untouched_buffer_takes_what_is_on_disk(tmp_path: Path):
    """Nothing to lose and nothing to decide."""
    where = a_workspace(tmp_path)
    window = Window()
    window.open_workspace(where)
    window.open_file(where / "main.tf")
    rewritten(where / "main.tf", "# changed elsewhere\n")
    window.check_files_on_disk()
    assert "changed elsewhere" in window._files_open.current.text()


def test_a_modified_buffer_is_never_overwritten_silently(tmp_path: Path):
    where = a_workspace(tmp_path)
    window = Window()
    window.open_workspace(where)
    window.open_file(where / "main.tf")
    page = window._files_open.current
    page.buffer.set_text("# mine\n")
    rewritten(where / "main.tf", "# theirs\n")
    window.check_files_on_disk()
    assert page.text() == "# mine\n"


def test_and_it_says_so_rather_than_saying_nothing(tmp_path: Path):
    where = a_workspace(tmp_path)
    window = Window()
    window.open_workspace(where)
    window.open_file(where / "main.tf")
    window._files_open.current.buffer.set_text("# mine\n")
    rewritten(where / "main.tf", "# theirs\n")
    offered = []
    window._offer_to_reload = offered.append
    window.check_files_on_disk()
    assert offered


def test_a_deleted_file_is_reported_and_kept_open(tmp_path: Path):
    where = a_workspace(tmp_path)
    window = Window()
    window.open_workspace(where)
    window.open_file(where / "main.tf")
    (where / "main.tf").unlink()
    window.check_files_on_disk()
    # A banner, not a toast: the file is still gone four seconds later.
    assert "deleted" in window._banner.get_title().lower()
    assert window._banner.get_revealed()
    assert window._files_open.pages


def test_it_asks_once_rather_than_on_every_focus(tmp_path: Path):
    where = a_workspace(tmp_path)
    window = Window()
    window.open_workspace(where)
    window.open_file(where / "main.tf")
    window._files_open.current.buffer.set_text("# mine\n")
    rewritten(where / "main.tf", "# theirs\n")
    offered = []
    real = window._offer_to_reload

    def spy(page):
        offered.append(page)
        real(page)

    window._offer_to_reload = spy
    window.check_files_on_disk()
    window.check_files_on_disk()
    assert len(offered) == 1


def test_typing_sets_the_buffer_aside(tmp_path: Path, monkeypatch):
    where = a_workspace(tmp_path)
    monkeypatch.setattr(recovery, "directory", lambda home=None: tmp_path / "kept")
    window = Window()
    window.open_workspace(where)
    window.open_file(where / "main.tf")
    window._files_open.current.buffer.set_text("# half typed\n")
    assert [f.text for f in recovery.waiting()] == ["# half typed\n"]


def test_a_clean_close_leaves_nothing_waiting(tmp_path: Path, monkeypatch):
    where = a_workspace(tmp_path)
    monkeypatch.setattr(recovery, "directory", lambda home=None: tmp_path / "kept")
    window = Window()
    window.open_workspace(where)
    window.open_file(where / "main.tf")
    window._files_open.current.buffer.set_text("# half typed\n")
    window.closing()
    assert recovery.waiting() == []


def test_recovering_puts_the_text_back_and_writes_nothing(tmp_path: Path, monkeypatch):
    """Recovering shows somebody their work; keeping it is theirs to decide."""
    where = a_workspace(tmp_path)
    monkeypatch.setattr(recovery, "directory", lambda home=None: tmp_path / "kept")
    original = (where / "main.tf").read_text(encoding="utf-8")
    recovery.keep(where / "main.tf", "# what was being typed\n")

    window = Window()
    window.open_workspace(where)
    window.recover(recovery.waiting())
    assert window._files_open.current.text() == "# what was being typed\n"
    assert (where / "main.tf").read_text(encoding="utf-8") == original


def test_autosave_writes_and_is_off_unless_asked_for(tmp_path: Path, monkeypatch):
    where = a_workspace(tmp_path)
    monkeypatch.setattr(recovery, "directory", lambda home=None: tmp_path / "kept")
    window = Window()
    window.open_workspace(where)
    window.open_file(where / "main.tf")
    page = window._files_open.current

    page.buffer.set_text("# not saved\n")
    assert "# not saved" not in (where / "main.tf").read_text(encoding="utf-8")

    window.settings = type(
        "Fixed", (), {"get": staticmethod(lambda key, default=None: key == "editor.autosave")}
    )()
    page.buffer.set_text("# saved by itself\n")
    assert "# saved by itself" in (where / "main.tf").read_text(encoding="utf-8")
