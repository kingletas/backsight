"""No refactor is offered as complete until a plan says it destroys nothing.

FR-REF-03. A refactor that produces a destroy and is offered anyway is a
build-breaking failure here, not a warning.
"""

import shutil
from pathlib import Path

import pytest
from corpus import cases

from backsight.engine.plan.model import Action
from backsight.engine.refactor.edits import apply_to
from backsight.engine.refactor.gate import Proposal, apply_refactor, verify
from backsight.engine.refactor.rename import Rename, edits_for, moved_block
from backsight.engine.runner import process

pytestmark = pytest.mark.skipif(
    shutil.which("tofu") is None, reason="the engine binary is not installed"
)

RENAME = Rename(resource_type="terraform_data", old_name="api", new_name="api_gateway")


def live_workspace(case, tmp_path: Path) -> Path:
    """A workspace with the `before` files applied, so there is real state."""
    directory = tmp_path / "workspace"
    shutil.copytree(case.before, directory)
    for command in (
        ["tofu", "init", "-no-color", "-input=false"],
        ["tofu", "apply", "-no-color", "-input=false", "-auto-approve"],
    ):
        result = process.start(command, cwd=directory).wait(180)
        assert result.ok, result.output
    return directory


def rename_proposal(directory: Path, *, with_moved: bool) -> Proposal:
    files = {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*.tf")}
    edits = edits_for(files, RENAME)
    appended = {}
    if with_moved:
        declared = next(
            relative for relative, data in files.items() if b'"api"' in data and b"resource" in data
        )
        appended[declared] = moved_block(RENAME)
    return Proposal(description="rename api to api_gateway", edits=edits, appended=appended)


def simple_case():
    return next(c for c in cases() if c.name == "rename-simple")


def test_a_rename_with_its_moved_block_is_accepted(tmp_path):
    directory = live_workspace(simple_case(), tmp_path)
    verdict = verify(
        rename_proposal(directory, with_moved=True), directory, scratch=tmp_path / "scratch"
    )
    assert verdict.accepted, verdict.reason
    assert verdict.plan.effective == ()
    assert "changes nothing" in verdict.reason


def test_the_same_rename_without_one_is_refused(tmp_path):
    """The single most important assertion in the project."""
    directory = live_workspace(simple_case(), tmp_path)
    verdict = verify(
        rename_proposal(directory, with_moved=False), directory, scratch=tmp_path / "scratch"
    )
    assert verdict.refused
    assert "would destroy" in verdict.reason
    assert "terraform_data.api" in verdict.destroyed


def test_a_refusal_names_what_would_have_been_destroyed(tmp_path):
    directory = live_workspace(simple_case(), tmp_path)
    verdict = verify(
        rename_proposal(directory, with_moved=False), directory, scratch=tmp_path / "scratch"
    )
    assert verdict.destroyed
    for address in verdict.destroyed:
        assert address in verdict.reason


def test_a_refused_refactor_leaves_the_files_exactly_as_they_were(tmp_path):
    """A refusal that has already written the files is not a refusal."""
    directory = live_workspace(simple_case(), tmp_path)
    before = {p: p.read_bytes() for p in sorted(directory.rglob("*.tf"))}
    verdict = apply_refactor(
        rename_proposal(directory, with_moved=False), directory, scratch=tmp_path / "scratch"
    )
    assert verdict.refused
    assert {p: p.read_bytes() for p in sorted(directory.rglob("*.tf"))} == before


def test_an_accepted_refactor_writes_the_files(tmp_path):
    directory = live_workspace(simple_case(), tmp_path)
    verdict = apply_refactor(
        rename_proposal(directory, with_moved=True), directory, scratch=tmp_path / "scratch"
    )
    assert verdict.accepted
    written = (directory / "main.tf").read_text()
    assert 'resource "terraform_data" "api_gateway"' in written
    assert "moved {" in written


def test_a_plan_that_will_not_run_is_a_refusal_and_not_an_approval(tmp_path):
    """Not knowing whether something is destructive is not knowing it is safe."""
    directory = live_workspace(simple_case(), tmp_path)
    broken = Proposal(
        description="something that does not parse",
        appended={Path("main.tf"): "\nthis is not HCL {{{\n"},
    )
    verdict = verify(broken, directory, scratch=tmp_path / "scratch")
    assert verdict.refused
    assert "could not run" in verdict.reason


def test_a_refactor_that_also_changes_something_is_refused(tmp_path):
    """A rename that also edits an argument is two operations; one was asked for."""
    directory = live_workspace(simple_case(), tmp_path)
    proposal = rename_proposal(directory, with_moved=True)
    files = {p.relative_to(directory): p.read_bytes() for p in directory.rglob("*.tf")}
    changed = {
        relative: apply_to(data, [e for e in proposal.edits if e.path == relative]).replace(
            b'"one"', b'"something else"'
        )
        for relative, data in files.items()
    }
    (directory / "main.tf").write_bytes(changed[Path("main.tf")])
    verdict = verify(
        Proposal(description="rename and edit", appended=proposal.appended),
        directory,
        scratch=tmp_path / "scratch",
    )
    assert verdict.refused
    assert "as well as move it" in verdict.reason


@pytest.mark.parametrize("case", [c for c in cases() if c.is_destructive], ids=lambda c: c.name)
def test_every_destructive_case_in_the_corpus_is_refused(case, tmp_path):
    """All four, driven from their own `after` files rather than from a rename.

    Whatever produced the change, the gate is what decides, and it decides on
    the plan rather than on what the change was called.
    """
    directory = live_workspace(case, tmp_path)
    # The `after` files are whole files, so each target is emptied and the whole
    # content appended. The gate sees the same bytes either way.
    appended: dict[Path, str] = {}
    for path in case.after.rglob("*.tf"):
        relative = path.relative_to(case.after)
        appended[relative] = path.read_text()
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"")
    verdict = verify(
        Proposal(description=case.description, appended=appended),
        directory,
        scratch=tmp_path / "scratch",
    )
    assert verdict.refused, f"{case.name} was accepted; the plan said {verdict.plan.summary()}"


def test_the_gate_reads_the_plan_and_not_the_intent(tmp_path):
    """A proposal that changes nothing at all is accepted, whatever it claims."""
    directory = live_workspace(simple_case(), tmp_path)
    verdict = verify(
        Proposal(description="claims to be a rename, does nothing"),
        directory,
        scratch=tmp_path / "scratch",
    )
    assert verdict.accepted
    assert all(c.action is Action.NO_OP for c in verdict.plan.changes)
