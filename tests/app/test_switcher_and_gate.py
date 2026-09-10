"""The header says where you are; the gate is the end of a page you have read."""

from __future__ import annotations

from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from backsight.app.apply_gate import ApplyGate  # noqa: E402
from backsight.app.switcher import (  # noqa: E402
    NOTHING_OPEN,
    OPEN_ANOTHER,
    THE_EXAMPLE,
    WorkspaceSwitcher,
)
from backsight.app.workspaces import Known, read, remember  # noqa: E402


def known(name: str, **kwargs) -> Known:
    return Known(path=Path("/invented") / name, **kwargs)


# --- the switcher ---------------------------------------------------------


def test_with_nothing_open_it_offers_only_the_two_ways_in():
    """The example lives here once the empty state stops treating it as equal."""
    switcher = WorkspaceSwitcher(on_example=lambda: None)
    switcher.show(None, [])
    # `rows` is the popover's list; the button itself says where you are.
    assert switcher.rows == [OPEN_ANOTHER, THE_EXAMPLE]
    assert switcher._name.get_label() == NOTHING_OPEN


def test_the_example_is_absent_once_there_are_workspaces():
    switcher = WorkspaceSwitcher(on_example=lambda: None)
    switcher.show(known("one"), [known("one")])
    assert THE_EXAMPLE not in switcher.rows


def test_opening_another_workspace_is_always_offered():
    switcher = WorkspaceSwitcher()
    switcher.show(known("one"), [known("one")])
    assert OPEN_ANOTHER in switcher.rows


def test_only_prod_earns_a_chip():
    """Inventing a colour for staging would say something that is not true."""
    switcher = WorkspaceSwitcher()
    switcher.show(known("a", environment="prod"), [])
    assert switcher._chip.get_visible()
    switcher.show(known("b", environment="staging"), [])
    assert not switcher._chip.get_visible()


def test_choosing_the_one_already_open_does_nothing():
    """It is not a no-op button; it is the row that says you are here."""
    asked: list[Path] = []
    switcher = WorkspaceSwitcher(on_open=asked.append)
    here = known("one")
    switcher.show(here, [here])
    switcher._choose(here.path)
    assert asked == []


def test_a_workspace_that_is_gone_says_so_instead_of_its_backend():
    """The absence is the useful information, and it is shown once."""
    assert "missing" in known("vanished", backend="s3").summary()


def test_the_state_summary_uses_the_consequence_vocabulary(tmp_path):
    """A real directory, because a missing one is its own state."""
    tmp_path.joinpath("w").mkdir()
    here = tmp_path / "w"
    assert Known(path=here, state="3 drifted").state_class == "tf-drift"
    assert Known(path=here, state="local state").state_class == "tf-nostate"
    assert Known(path=here, state="clean").state_class == "tf-faint"


def test_a_workspace_that_is_gone_has_no_state_to_describe():
    assert known("vanished", state="clean").state_class == "tf-nostate"


def test_the_list_is_capped_and_newest_first(tmp_path):
    for index in range(12):
        directory = tmp_path / f"w{index}"
        directory.mkdir()
        remember(Known(path=directory), home=tmp_path)
    found = read(home=tmp_path)
    assert len(found) == 8
    assert found[0].path.name == "w11"


def test_a_workspace_that_no_longer_exists_is_dropped_on_the_next_write(tmp_path):
    gone = tmp_path / "gone"
    gone.mkdir()
    remember(Known(path=gone), home=tmp_path)
    gone.rmdir()
    here = tmp_path / "here"
    here.mkdir()
    remember(Known(path=here), home=tmp_path)
    assert [k.path.name for k in read(home=tmp_path)] == ["here"]


# --- the gate -------------------------------------------------------------


PLAN = object()


def ready(**changed):
    """A plan that could be applied, with anything about it overridden."""
    from backsight.engine.plan.footer import Situation

    return Situation(**{"plan": PLAN, "changes": 3, **changed})


def test_a_blocker_names_itself_and_offers_the_reading_instead():
    """Apply cannot work, so the footer does not show an Apply that cannot work."""
    gate = ApplyGate()
    gate.show(ready(irreversible=2, blocked="Credentials are needed to apply"))
    assert not gate.can_apply
    assert gate.action == "Review 3 changes"
    assert gate.hint == "Credentials are needed to apply"


def test_no_supporting_text_asks_the_reader_to_go_and_find_the_blocker():
    """ "Resolve what is blocking apply first" names no blocker."""
    import re

    from backsight.app import apply_gate

    said = [v for k, v in vars(apply_gate).items() if k.isupper() and isinstance(v, str)]
    assert not [s for s in said if re.search(r"what is blocking", s)]


def test_an_irreversible_plan_has_to_be_typed_out():
    """A checkbox is one click, and so is the mistake."""
    gate = ApplyGate()
    gate.show(ready(irreversible=2, environment="prod"))
    assert not gate.can_apply
    assert "prod" in gate.hint
    gate._confirm.set_text("prod")
    assert gate.can_apply
    assert gate.hint == "2 irreversible"


def test_typing_the_wrong_thing_does_not_unlock_it():
    gate = ApplyGate()
    gate.show(ready(irreversible=1, environment="prod"))
    gate._confirm.set_text("production")
    assert not gate.can_apply


def test_a_plan_with_nothing_irreversible_is_not_made_to_type():
    """Asking for it every time teaches people to type without reading."""
    gate = ApplyGate()
    gate.show(ready(environment="prod"))
    assert not gate._confirm.get_visible()
    assert gate.can_apply


def test_the_button_is_neutral_until_the_plan_is_irreversible():
    """A permanently red Apply trains people to ignore red."""
    gate = ApplyGate()
    gate.show(ready(environment="prod"))
    assert "tf-irreversible" not in gate._button.get_css_classes()
    gate.show(ready(irreversible=1, environment="prod"))
    assert "tf-irreversible" in gate._button.get_css_classes()


def test_applying_before_the_environment_is_typed_reaches_nobody():
    ran: list[str] = []
    gate = ApplyGate(on_apply=lambda: ran.append("applied"))
    gate.show(ready(irreversible=1, environment="prod"))
    gate._pressed()
    assert ran == []


def test_apply_is_absent_rather_than_dead_when_the_plan_failed():
    """A permanently disabled primary action makes the footer scenery."""
    from backsight.engine.plan.diagnostics import Diagnostic
    from backsight.engine.plan.footer import Situation

    gate = ApplyGate()
    gate.show(Situation(errors=[Diagnostic(severity="Error", summary="x", path="main.tf", line=2)]))
    assert gate.action == "Re-plan"
    assert not gate.can_apply
    assert gate._button.get_sensitive(), "the primary action is never disabled"


def test_a_plan_that_changes_nothing_has_no_footer_at_all():
    gate = ApplyGate()
    gate.show(ready(changes=0))
    assert not gate.get_visible()
    assert gate.action == ""


def test_the_footer_action_runs_the_command_it_names():
    ran: list[str] = []
    gate = ApplyGate()
    gate.on_command(ran.append)
    from backsight.engine.plan.footer import Situation

    gate.show(Situation())
    assert gate.action == "Run plan"
    gate._pressed()
    assert ran == ["plan-now"]


def test_the_status_bar_and_the_footer_never_disagree_about_apply():
    """The status bar carried a hardcoded "credentials needed to apply" while
    the footer worked out the truth, so a plan that could be applied said both
    at once."""
    import pytest

    gi = pytest.importorskip("gi", reason="the toolkit is not installed")
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")

    from backsight.app.window import Window
    from backsight.engine.insight.sections import why_apply_is_blocked
    from backsight.engine.plan.model import Action, Plan, ResourceChange

    plan = Plan(
        format_version="1.2",
        engine_version="1.12.6",
        changes=(ResourceChange("a.b", "a", "b", "managed", "terraform", Action.CREATE),),
    )
    window = Window()
    window._plan = plan
    expected = why_apply_is_blocked(plan, window._capabilities(), 1) or ""
    assert window._situation().blocked == expected
    assert expected == ""
