"""Saving repeatedly produces one plan, and never an old answer.

The failure this guards against is quiet: an earlier plan finishing after a
later one and overwriting a current answer with a stale one. Nothing on the
screen would say it happened.
"""

import shutil
import statistics
import threading
import time
from pathlib import Path

import pytest

from backsight.engine.plan.execution import PlanOutcome, speculative
from backsight.engine.plan.model import Plan
from backsight.engine.plan.speculation import Speculator, Stage
from backsight.engine.runner.process import RunState

# NFR-07 allows fifteen seconds at the median for a workspace of this size.
BUDGET_SECONDS = 15
RESOURCES = 200


def fake_plan(seconds: float = 0.0, ok: bool = True):
    """A stand-in that takes a known time, so the scheduling is what is measured."""
    calls: list[float] = []

    def run(directory, **_kwargs) -> PlanOutcome:
        calls.append(time.perf_counter())
        time.sleep(seconds)
        return PlanOutcome(
            plan=Plan(format_version="1.2", engine_version="test") if ok else None,
            artifact=None,
            output="",
            state=RunState.SUCCEEDED if ok else RunState.FAILED,
            seconds=seconds,
        )

    run.calls = calls
    return run


def test_one_save_produces_one_plan(tmp_path):
    plans = []
    run = fake_plan()
    speculator = Speculator(tmp_path, debounce=0.05, plan=run, on_plan=plans.append)
    speculator.touched()
    speculator.wait(5)
    time.sleep(0.2)
    assert len(run.calls) == 1
    assert len(plans) == 1


def test_rapid_saves_produce_exactly_one_plan(tmp_path):
    """The whole point of the debounce. Ten saves, one plan."""
    plans = []
    run = fake_plan()
    speculator = Speculator(tmp_path, debounce=0.3, plan=run, on_plan=plans.append)
    for _ in range(10):
        speculator.touched()
        time.sleep(0.02)
    speculator.wait(5)
    time.sleep(0.3)
    assert len(run.calls) == 1, f"{len(run.calls)} plans ran; the debounce is not holding"
    assert len(plans) == 1


def test_a_save_during_a_running_plan_supersedes_it(tmp_path):
    """The older plan must not report. It is answering about a file that changed."""
    plans = []
    run = fake_plan(seconds=0.5)
    speculator = Speculator(tmp_path, debounce=0.05, plan=run, on_plan=plans.append)
    speculator.touched()
    time.sleep(0.25)  # the first plan is now in flight
    assert speculator.stage is Stage.RUNNING
    speculator.touched()
    speculator.wait(10)
    time.sleep(1.0)
    assert len(run.calls) == 2, "the second save should have started a second plan"
    assert len(plans) == 1, "the superseded plan reported anyway"


def test_the_stage_says_what_is_happening(tmp_path):
    seen = []
    speculator = Speculator(
        tmp_path, debounce=0.05, plan=fake_plan(), on_progress=lambda p: seen.append(p.stage)
    )
    speculator.touched()
    speculator.wait(5)
    time.sleep(0.2)
    assert seen[0] is Stage.WAITING
    assert Stage.RUNNING in seen
    assert seen[-1] is Stage.DONE


def test_a_failing_plan_says_so_rather_than_going_quiet(tmp_path):
    seen = []
    speculator = Speculator(
        tmp_path,
        debounce=0.05,
        plan=fake_plan(ok=False),
        on_progress=lambda p: seen.append(p.stage),
    )
    speculator.touched()
    speculator.wait(5)
    time.sleep(0.2)
    assert seen[-1] is Stage.FAILED


def test_cancelling_stops_a_pending_plan(tmp_path):
    run = fake_plan()
    speculator = Speculator(tmp_path, debounce=0.4, plan=run)
    speculator.touched()
    speculator.cancel()
    time.sleep(0.6)
    assert run.calls == []
    assert speculator.stage is Stage.IDLE


def test_saves_from_several_threads_still_produce_one_plan(tmp_path):
    """An editor saving several open files at once is the ordinary case."""
    plans = []
    run = fake_plan()
    speculator = Speculator(tmp_path, debounce=0.3, plan=run, on_plan=plans.append)
    threads = [threading.Thread(target=speculator.touched) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    speculator.wait(5)
    time.sleep(0.4)
    assert len(run.calls) == 1
    assert len(plans) == 1


@pytest.mark.skipif(shutil.which("tofu") is None, reason="the engine binary is not installed")
def test_a_two_hundred_resource_workspace_plans_inside_its_budget(tmp_path):
    """NFR-07, measured.

    Built from the engine's own `terraform_data`, so it needs no provider and no
    network. That makes this a floor rather than a forecast: it shows the
    orchestration is not the cost. A real workspace adds provider round trips,
    and that number can only be taken against a real account.
    """
    body = "\n".join(
        f'resource "terraform_data" "r{n}" {{\n  input = "value-{n}"\n}}\n'
        for n in range(RESOURCES)
    )
    (tmp_path / "main.tf").write_text(body)

    timings = []
    for _ in range(3):
        started = time.perf_counter()
        outcome = speculative(tmp_path)
        timings.append(time.perf_counter() - started)
        assert outcome.ok, outcome.output
        assert len(outcome.plan.changes) == RESOURCES

    median = statistics.median(timings)
    print(f"\n  {RESOURCES} resources: p50 {median:.2f}s over {len(timings)} runs")
    assert median < BUDGET_SECONDS, f"p50 was {median:.1f}s against a {BUDGET_SECONDS}s budget"


def test_asking_for_a_plan_does_not_wait_out_the_debounce(tmp_path):
    """The clock turns a burst of saves into one plan. Somebody who pressed
    Run plan has already stopped typing."""
    run = fake_plan()
    speculator = Speculator(tmp_path, debounce=5.0, plan=run)
    began = time.perf_counter()
    speculator.now()
    speculator.wait(timeout=5)
    assert run.calls
    assert time.perf_counter() - began < 1.0


def test_asking_cancels_a_clock_that_was_already_running(tmp_path):
    """Otherwise the debounce fires afterwards and plans the same file twice."""
    run = fake_plan()
    speculator = Speculator(tmp_path, debounce=0.2, plan=run)
    speculator.touched()
    speculator.now()
    time.sleep(0.6)
    speculator.wait(timeout=5)
    assert len(run.calls) == 1


def test_cancelling_stops_the_engine_rather_than_ignoring_it(tmp_path):
    """It bumped a generation counter and discarded the answer while `tofu`
    kept running — holding the state lock, for a run nobody was waiting for.

    A real subprocess, because the whole defect was that the handle never left
    the function that started it, and a fake plan cannot show that.
    """
    from backsight.engine.runner import process

    seen = {}

    def slow(directory, started=None, **_kwargs):
        run = process.start(["sleep", "30"], cwd=tmp_path, timeout=60)
        seen["pid"] = run._process.pid
        if started is not None:
            started(run)
        result = run.wait()
        return PlanOutcome(plan=None, artifact=None, output="", state=result.state, seconds=0.0)

    speculator = Speculator(tmp_path, debounce=0.0, plan=slow)
    speculator.now()
    for _ in range(200):
        if "pid" in seen:
            break
        time.sleep(0.01)
    alive = Path(f"/proc/{seen['pid']}")
    assert alive.exists()

    speculator.cancel()
    for _ in range(200):
        if not alive.exists():
            break
        time.sleep(0.01)
    assert not alive.exists(), "cancelling left the engine running"
