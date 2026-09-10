"""`init`, `validate` and `fmt`, through the application, against the emulator.

Each case calls the function the application calls. Nothing here runs the engine
to make something happen — the direct CLI appears only where a fixture has to be
set up or an answer verified.
"""

from __future__ import annotations

import pytest

from backsight.engine.plan import commands

pytestmark = pytest.mark.usefixtures("emulator")


# --- init -------------------------------------------------------------------


def test_init_installs_the_provider_and_says_it_worked(workspace):
    """The application's `initialise`, which is what the Initialise command runs."""
    said = commands.initialise(workspace.path, binary=workspace.engine)

    assert said is not None, "the engine did not answer"
    assert said.ok, said.err or said.out
    assert (workspace.path / ".terraform").is_dir(), "nothing was installed"
    assert (workspace.path / ".terraform.lock.hcl").is_file(), "no lock file was written"


def test_init_leaves_a_lock_file_that_pins_what_it_installed(workspace):
    """Determinism is the point of the lock file, and a run that does not write
    one is a run whose next run is about a different provider."""
    commands.initialise(workspace.path, binary=workspace.engine)
    locked = (workspace.path / ".terraform.lock.hcl").read_text(encoding="utf-8")
    assert "hashicorp/aws" in locked
    assert "version" in locked


@pytest.mark.fixture_name("unreachable")
def test_init_fails_readably_when_the_provider_does_not_exist(workspace):
    """**The negative case, and it is the one worth having.** A checker that has
    only ever been seen succeeding has not been tested."""
    said = commands.initialise(workspace.path, binary=workspace.engine)

    assert said is not None
    assert not said.ok, "a provider that does not exist installed successfully"
    complaint = (said.err + said.out).lower()
    assert "provider" in complaint
    assert not (workspace.path / ".terraform.lock.hcl").exists()


# --- validate ---------------------------------------------------------------


def test_validate_passes_a_configuration_that_is_sound(workspace):
    commands.initialise(workspace.path, binary=workspace.engine)
    said = commands.validate(workspace.path, binary=workspace.engine)

    assert said.valid, said.output
    assert not said.problems


@pytest.mark.fixture_name("invalid")
def test_validate_refuses_a_configuration_that_is_not(workspace):
    """Two different faults on purpose: an argument the schema does not have,
    and a reference to a resource nobody declared."""
    commands.initialise(workspace.path, binary=workspace.engine)
    said = commands.validate(workspace.path, binary=workspace.engine)

    assert not said.valid
    assert said.problems, "it refused the configuration without saying why"


@pytest.mark.fixture_name("invalid")
def test_a_problem_says_where_it_is(workspace):
    """A finding the author cannot locate is a finding they will not fix."""
    commands.initialise(workspace.path, binary=workspace.engine)
    said = commands.validate(workspace.path, binary=workspace.engine)

    located = [one for one in said.problems if one.line]
    assert located, f"nothing carried a line: {[one.summary for one in said.problems]}"
    assert all(one.summary for one in said.problems)


def test_validate_before_init_is_a_state_rather_than_a_crash(workspace):
    """The ordinary first thing somebody does wrong, and it must read as a
    state — the application offers init from the same footer."""
    said = commands.validate(workspace.path, binary=workspace.engine)
    assert not said.valid
    assert said.output or said.problems


# --- fmt --------------------------------------------------------------------


def test_fmt_check_is_quiet_about_a_file_that_is_already_formatted(workspace):
    said = commands.formatting(workspace.path, binary=workspace.engine)
    assert said.tidy, said.diff


@pytest.mark.fixture_name("unformatted")
def test_fmt_check_names_the_file_it_would_change(workspace):
    said = commands.formatting(workspace.path, binary=workspace.engine)

    assert not said.tidy
    assert "main.tf" in (said.diff + " ".join(said.files))


@pytest.mark.fixture_name("unformatted")
def test_fmt_check_changes_nothing_on_disk(workspace):
    """**The promise the README opens with.** `-check` reports; it does not
    rewrite, and a check that quietly reformats somebody's file is the one
    defect this application must never have."""
    before = (workspace.path / "main.tf").read_bytes()
    commands.formatting(workspace.path, binary=workspace.engine)
    assert (workspace.path / "main.tf").read_bytes() == before


def test_formatting_text_returns_the_tidied_version(workspace):
    """The other `fmt` the application runs: one buffer, over stdin, never a
    file on disk."""
    said = commands.format_text(
        'resource   "aws_s3_bucket"  "x" {\n  bucket="y"\n}\n',
        directory=workspace.path,
        binary=workspace.engine,
    )
    assert said.ok, said.complaint
    assert said.changed_anything
    assert 'resource "aws_s3_bucket" "x"' in said.text
    assert 'bucket = "y"' in said.text


def test_formatting_text_that_will_not_parse_leaves_it_exactly_alone(workspace):
    """A file mid-edit is not valid HCL for keystrokes at a time, and the one
    thing formatting may never do is mangle it."""
    broken = 'resource "aws_s3_bucket" "x" {\n  bucket = \n'
    said = commands.format_text(broken, directory=workspace.path, binary=workspace.engine)
    assert not said.ok, "it formatted something that does not parse"
    assert not said.changed_anything, "a partial result would be worse than none"
    assert said.complaint, "it refused without saying why"
