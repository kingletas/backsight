"""The `no backend` row, opened."""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

from backsight.app.backend_dialog import HOW, NOTHING_YET, BackendDialog  # noqa: E402
from backsight.engine.workspace.backend import WITHOUT_A_BACKEND, local_state  # noqa: E402

Adw.init()

CAPTURED = Path(__file__).resolve().parents[2] / "fixtures" / "local-state"


def test_it_says_what_was_found_and_where():
    said = BackendDialog("prod", local_state(CAPTURED)).says
    assert any("2 resources" in line for line in said)
    assert any("terraform.tfstate" in line for line in said)


def test_it_names_every_thing_that_is_lost():
    said = BackendDialog("prod", local_state(CAPTURED)).says
    for cost in WITHOUT_A_BACKEND:
        assert cost in said


def test_nothing_created_yet_is_a_different_situation(tmp_path: Path):
    said = BackendDialog("prod", None).says
    assert NOTHING_YET in said


def test_it_does_not_offer_a_migration_it_cannot_perform():
    """A button that cannot work is the greyed Apply, wearing another label."""
    dialog = BackendDialog("prod", local_state(CAPTURED))
    assert HOW in dialog.says
    assert not [line for line in dialog.says if line.startswith("Migrate")]
