"""The detail behind `3 drifted`, which used to go nowhere."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.drift_panel import DriftPanel  # noqa: E402
from backsight.engine.plan.drifting import Drift, from_document, from_stream  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "drift"


def document() -> dict:
    return json.loads((FIXTURES / "refresh-only-plan.json").read_text(encoding="utf-8"))


def stream(name: str) -> list[str]:
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


def test_before_a_check_it_says_what_would_fill_it():
    panel = DriftPanel()
    assert "Run a drift check" in panel.headline
    assert panel.addresses() == []


def test_a_clean_check_says_nothing_has_changed_rather_than_staying_blank():
    panel = DriftPanel()
    panel.show(from_stream(stream("none.jsonl")))
    assert panel.headline == "Nothing has changed outside Terraform"
    assert panel.addresses() == []


def test_it_names_every_resource_that_moved():
    panel = DriftPanel()
    panel.show(from_document(document()))
    assert panel.addresses() == ["local_file.config", "local_file.notes"]


def test_clicking_a_resource_asks_to_open_where_it_is_declared():
    went = []
    panel = DriftPanel(on_open=went.append)
    panel.show(from_document(document()))
    child = panel._rows.get_first_child()
    child.get_first_child().emit("clicked")
    assert went == ["local_file.config"]


def test_a_check_that_could_not_run_says_so_rather_than_looking_clean():
    """Reporting a failed check as "nothing has changed" is the worst answer a
    checker can give."""
    panel = DriftPanel()
    panel.show(Drift(failure="No valid credential sources found"))
    assert panel.headline == "No valid credential sources found"


def test_the_panel_redraws_rather_than_accumulating():
    panel = DriftPanel()
    panel.show(from_document(document()))
    panel.show(from_document(document()))
    assert panel.addresses() == ["local_file.config", "local_file.notes"]


def test_a_drift_timer_only_runs_when_somebody_asked_for_one():
    """Off by default: a refresh costs a provider call per resource, and
    starting that against somebody's account unasked is not ours to decide."""
    from backsight.app.window import Window
    from backsight.engine.settings.layers import DEFAULTS

    window = Window()
    assert DEFAULTS["analysis.drift_every_minutes"] == 0
    window._start_watching_for_drift()
    assert window._drift_timer is None


def test_asking_for_one_starts_it(tmp_path):
    from backsight.app.window import Window
    from backsight.engine.settings.layers import DEFAULTS, Settings

    window = Window()
    window.settings = Settings(
        layers={"default": dict(DEFAULTS), "user": {"analysis.drift_every_minutes": 30}}
    )
    window.workspace = object()
    window._start_watching_for_drift()
    assert window._drift_timer is not None
    window._start_watching_for_drift()
    assert window._drift_timer is not None


def test_turning_it_off_stops_it(tmp_path):
    from backsight.app.window import Window
    from backsight.engine.settings.layers import DEFAULTS, Settings

    window = Window()
    window.settings = Settings(
        layers={"default": dict(DEFAULTS), "user": {"analysis.drift_every_minutes": 30}}
    )
    window.workspace = object()
    window._start_watching_for_drift()
    window.settings = Settings(layers={"default": dict(DEFAULTS)})
    window._start_watching_for_drift()
    assert window._drift_timer is None
