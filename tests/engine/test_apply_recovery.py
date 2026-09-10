"""An apply that was killed part-way is noticed, and nothing is done about it.

FR-ST-05. The failure to avoid is a silent re-plan: a plan against a state that
may be wrong gives a confident answer about a situation nobody has looked at.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from backsight.engine.actor import Actor, ActorKind
from backsight.engine.plan.recovery import MARKER, begin, finish, interrupted

WHO = Actor(kind=ActorKind.PERSON, identifier="someone")


def test_a_workspace_with_no_marker_has_nothing_to_recover(tmp_path):
    assert interrupted(tmp_path) is None


def test_an_apply_that_finished_leaves_nothing_behind(tmp_path):
    begin(tmp_path, plan_digest="abc123", actor=WHO)
    finish(tmp_path)
    assert interrupted(tmp_path) is None


def test_finishing_twice_is_not_an_error(tmp_path):
    begin(tmp_path, plan_digest="abc123", actor=WHO)
    finish(tmp_path)
    finish(tmp_path)
    assert interrupted(tmp_path) is None


def test_an_apply_killed_part_way_is_found_on_the_next_launch(tmp_path):
    """The acceptance: a real process is killed mid-apply and the marker remains."""
    script = (
        "import sys, time\n"
        f"sys.path.insert(0, {str(Path(__file__).resolve().parents[2] / 'src')!r})\n"
        "from backsight.engine.actor import Actor, ActorKind\n"
        "from backsight.engine.plan.recovery import begin, finish\n"
        f"begin({str(tmp_path)!r}, plan_digest='deadbeef',"
        " actor=Actor(kind=ActorKind.PERSON, identifier='someone'))\n"
        "print('started', flush=True)\n"
        "time.sleep(30)\n"
        "finish()\n"
    )
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-u", "-c", script], stdout=subprocess.PIPE, text=True
    )
    assert process.stdout.readline().strip() == "started"
    process.kill()
    process.wait(10)

    found = interrupted(tmp_path)
    assert found is not None, "the interrupted apply left no trace"
    assert found.plan_digest == "deadbeef"
    assert found.actor == "someone"
    assert found.still_running is False


def test_the_next_launch_does_not_recover_anything_by_itself(tmp_path):
    """Detecting is the whole job. Acting on it is the user's."""
    begin(tmp_path, plan_digest="abc123", actor=WHO)
    found = interrupted(tmp_path)
    # Looking at it changes nothing, and the marker is still there afterwards.
    assert found.guidance()
    assert (tmp_path / MARKER).is_file()
    assert interrupted(tmp_path) is not None


def test_the_guidance_says_plainly_that_nothing_was_done(tmp_path):
    begin(tmp_path, plan_digest="abc123", actor=WHO)
    said = " ".join(interrupted(tmp_path).guidance())
    assert "may not agree" in said
    assert "Nothing has been re-planned or reconciled for you" in said


def test_an_apply_that_is_still_running_is_not_reported_as_interrupted(tmp_path):
    """This process is alive, so the apply it recorded has not been interrupted."""
    begin(tmp_path, plan_digest="abc123", actor=WHO)
    assert interrupted(tmp_path).still_running is True


def test_a_half_written_marker_is_still_evidence(tmp_path):
    """A crash during the write should not make the crash invisible."""
    marker = tmp_path / MARKER
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"format": 1, "started_at": "2026')
    found = interrupted(tmp_path)
    assert found is not None
    assert found.plan_digest == "unknown"


def test_the_marker_records_who_was_responsible(tmp_path):
    """A service applying for a person records the person, per the actor rule."""
    on_behalf = Actor(kind=ActorKind.SERVICE, identifier="hub", on_behalf_of="j.okafor")
    begin(tmp_path, plan_digest="abc123", actor=on_behalf)
    assert interrupted(tmp_path).actor == "j.okafor"


def test_the_marker_is_readable_by_a_person(tmp_path):
    begin(tmp_path, plan_digest="abc123", actor=WHO, output_path=tmp_path / "apply.log")
    recorded = json.loads((tmp_path / MARKER).read_text())
    assert recorded["format"] == 1
    assert recorded["plan_digest"] == "abc123"
    assert recorded["process_id"] == os.getpid()
    assert recorded["output_path"].endswith("apply.log")


def test_the_recorded_time_is_when_it_started(tmp_path):
    before = time.time()
    begin(tmp_path, plan_digest="abc123", actor=WHO)
    started = interrupted(tmp_path).started_at.timestamp()
    assert before - 1 <= started <= time.time() + 1
