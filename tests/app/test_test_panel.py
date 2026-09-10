"""What the test panel says, and that it never overstates a green run."""

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")

from backsight.app.test_panel import MARKS, TONES  # noqa: E402
from backsight.engine.tests.execution import Target  # noqa: E402
from backsight.engine.tests.results import Status, parse  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RESULTS = parse((ROOT / "fixtures" / "tests" / "run-with-a-failure.jsonl").read_text())


def test_every_status_has_a_shape_of_its_own():
    """NFR-15: a run's state survives a monochrome screenshot."""
    assert len(set(MARKS.values())) == len(MARKS)
    assert set(MARKS) == set(TONES) == set(Status)


def test_pass_and_fail_do_not_share_a_tone():
    assert TONES[Status.PASSED] != TONES[Status.FAILED]


def test_the_panel_renders_a_real_result(monkeypatch):
    from backsight.app.test_panel import TestPanel

    panel = TestPanel()
    panel.show(RESULTS, target=Target.MOCKS)
    labels = _labels(panel)
    assert "tests/nodes.tftest.hcl" in labels
    assert "creates_the_right_number" in labels
    assert "names_are_wrong_on_purpose" in labels


def test_the_evaluated_values_reach_the_screen():
    """FR-TST-03. This one line is the whole reason the feature exists."""
    from backsight.app.test_panel import TestPanel

    panel = TestPanel()
    panel.show(RESULTS)
    assert "terraform_data.nodes is tuple with 3 elements" in _labels(panel)


def test_the_condition_is_shown_beside_its_values():
    from backsight.app.test_panel import TestPanel

    panel = TestPanel()
    panel.show(RESULTS)
    assert any("length(terraform_data.nodes) == 5" in label for label in _labels(panel))


def test_the_target_is_stated_on_every_result():
    """A green run against mocks and a green run against an account are not
    the same claim, so the panel never shows one without saying which."""
    from backsight.app.test_panel import TestPanel

    for target in Target:
        panel = TestPanel()
        panel.show(RESULTS, target=target)
        assert any(f"Ran against {target.value}" in label for label in _labels(panel))


def test_a_panel_with_nothing_run_says_so():
    from backsight.app.test_panel import TestPanel

    panel = TestPanel()
    assert "No tests have run" in _labels(panel)


def _labels(widget) -> list[str]:
    found = []

    def walk(current) -> None:
        if isinstance(current, gi.repository.Gtk.Label):
            found.append(current.get_label() or "")
        child = current.get_first_child()
        while child is not None:
            walk(child)
            child = child.get_next_sibling()

    walk(widget)
    return found
