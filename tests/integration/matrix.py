"""What each engine command is tested with, and how the result is checked.

**The rows come from the application, not from a brief.** `invocations.found_in`
walks the package and reports every argument list handed to the engine; this
says, for each of them, which fixture it runs against, what is expected and how
that is verified. A test asserts the two agree, so adding a command without
testing it fails the build rather than quietly widening a gap.

`service` is the emulator service the command needs. **`—` means it needs none**
— `fmt` reads text, `console` evaluates an expression, `version` asks the binary
about itself — and saying so is the difference between a command that is out of
scope for the emulator and one nobody got round to.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Row:
    """One engine command, and what proves the application drives it."""

    command: str
    invoked_by: str
    fixture: str
    expects: str
    verified_by: str
    service: str = "—"
    tests: tuple[str, ...] = field(default_factory=tuple)


MATRIX: tuple[Row, ...] = (
    Row(
        command="init",
        invoked_by="plan.commands.initialise",
        fixture="base",
        expects="the provider is installed and a lock file is written",
        verified_by="`.terraform/` and `.terraform.lock.hcl` on disk",
        tests=(
            "init_installs_the_provider_and_says_it_worked",
            "init_leaves_a_lock_file_that_pins_what_it_installed",
            "init_fails_readably_when_the_provider_does_not_exist",
        ),
    ),
    Row(
        command="validate",
        invoked_by="plan.commands.validate",
        fixture="base, invalid",
        expects="sound passes; an unknown argument and a dangling reference do not",
        verified_by="`Validation.valid`, and every problem carries a line",
        tests=(
            "validate_passes_a_configuration_that_is_sound",
            "validate_refuses_a_configuration_that_is_not",
            "a_problem_says_where_it_is",
            "validate_before_init_is_a_state_rather_than_a_crash",
        ),
    ),
    Row(
        command="fmt",
        invoked_by="plan.commands.formatting, plan.commands.format_text",
        fixture="base, unformatted",
        expects="`-check` names the file and rewrites nothing; stdin returns the tidied text",
        verified_by="the file's bytes before and after, and the returned text",
        tests=(
            "fmt_check_is_quiet_about_a_file_that_is_already_formatted",
            "fmt_check_names_the_file_it_would_change",
            "fmt_check_changes_nothing_on_disk",
            "formatting_text_returns_the_tidied_version",
            "formatting_text_that_will_not_parse_leaves_it_exactly_alone",
        ),
    ),
    Row(
        command="plan",
        invoked_by="plan.execution.speculative",
        fixture="base, invalid",
        expects="three creates, an artifact on disk, and nothing to do on a second run",
        verified_by="`Plan.effective` and the artifact file",
        service="s3, sqs, dynamodb, sts",
        tests=(
            "plan_reads_back_what_it_would_create",
            "the_artifact_is_written_where_the_apply_will_look_for_it",
            "a_plan_that_cannot_run_says_why_and_produces_nothing",
            "planning_an_applied_configuration_again_finds_nothing_to_do",
        ),
    ),
    Row(
        command="apply",
        invoked_by="plan.applying.run",
        fixture="base",
        expects="the objects exist; an update reaches the service; a destroy removes them",
        verified_by="**the emulator's own API** — list_buckets, list_queues, list_tables",
        service="s3, sqs, dynamodb",
        tests=(
            "apply_creates_what_the_plan_said_and_the_emulator_agrees",
            "apply_reports_each_resource_as_it_moves",
            "an_update_reaches_the_service_and_not_only_the_state",
            "destroying_removes_the_objects_from_the_emulator",
        ),
    ),
    Row(
        command="show",
        invoked_by="plan.commands.state, plan.execution.speculative, plan.drifting.check",
        fixture="base, outputs",
        expects="state names what was created; outputs come back with their types",
        verified_by="`State.resources`, and the parsed `values.outputs`",
        service="s3, sqs, dynamodb",
        tests=(
            "the_state_the_application_reads_names_what_was_created",
            "the_state_of_a_workspace_with_nothing_in_it_says_so",
            "outputs_come_back_out_of_the_state_with_their_types",
        ),
    ),
    Row(
        command="plan -refresh-only",
        invoked_by="plan.drifting.check",
        fixture="base, outputs",
        expects="a change made through the API is found; an untouched workspace is quiet",
        verified_by="`Drift.resources`, after the queue is changed through SQS itself",
        service="sqs",
        tests=(
            "a_change_made_outside_terraform_is_found_by_a_drift_check",
            "a_drift_check_over_untouched_infrastructure_finds_nothing",
            "a_drift_check_changes_nothing",
            "the_aws_provider_reports_an_unset_tag_map_as_a_difference",
        ),
    ),
    Row(
        command="console",
        invoked_by="console.evaluation.evaluate",
        fixture="outputs",
        expects="an expression evaluates; an unknown reference says what is wrong",
        verified_by="`Evaluation.value` and `Evaluation.failure`",
        tests=(
            "the_console_evaluates_an_expression_against_the_workspace",
            "it_reads_a_variable_the_configuration_declares",
            "an_expression_that_will_not_evaluate_says_what_is_wrong",
            "an_empty_expression_is_refused_without_starting_anything",
        ),
    ),
    Row(
        command="test",
        invoked_by="tests.execution.run",
        fixture="tests",
        expects="a passing file passes; a failing file is reported as failing",
        verified_by="`Results.passed`/`failed`, and the failure's own message",
        tests=(
            "the_runner_finds_the_test_files_the_way_the_tree_shows_them",
            "a_passing_run_reports_each_assertion_as_passed",
            "a_failing_run_is_reported_as_failing_rather_than_as_nothing",
            "a_failure_says_which_assertion_and_what_it_expected",
            "running_against_a_real_account_is_refused_without_being_confirmed",
        ),
    ),
    Row(
        command="version",
        invoked_by="app.window._engine_version",
        fixture="base",
        expects="the binary says which version it is",
        verified_by="the JSON carries `terraform_version`",
        tests=("the_engine_says_which_version_it_is",),
    ),
)

# What the application does **not** run, discovered by the same walk finding
# nothing. Named rather than left out: a reader comparing this against
# Terraform's own command list needs to know the absence is a finding.
NOT_RUN = {
    "destroy": (
        "Destruction is applying a plan that destroys, which is the promise that "
        "what runs is what was reviewed. There is no separate destroy path to test, "
        "and the destroy case above goes through `apply`."
    ),
    "output": (
        "Outputs are read out of `show -json`, which the application already "
        "runs for state — so there is no separate `output` invocation to test."
    ),
    "state": (
        "State is read the same way, through `show -json`. Nothing here mutates "
        "state: `state mv` and `state rm` rewrite what exists without touching "
        "the infrastructure, which is the sharpest edge in the whole tool."
    ),
    "refresh": (
        "Done as `plan -refresh-only`, deliberately: that is read-only, and "
        "`refresh` writes the state file. A drift check must not change anything."
    ),
    "workspace": (
        "Named workspaces are not a concept this application exposes anywhere — "
        "it works on root modules and stacks, and there is no command, menu "
        "item or setting that reaches `workspace select`."
    ),
    "providers": (
        "The provider schema is read from a committed `providers schema -json` "
        "capture rather than by running the command."
    ),
    "graph": (
        "Never run. The dependency picture this application draws is the stack "
        "graph, which it computes itself and offline."
    ),
    "import": "Named in a menu and blocked: the id format is not in the provider schema.",
    "force-unlock": (
        "Never run. A held lock is surfaced so somebody can find out who holds "
        "it; breaking one from a desktop editor is not a decision this makes."
    ),
    "taint": (
        "Never run. It is superseded by `-replace` on a plan, and the "
        "application has no path that asks for either."
    ),
    "login": (
        "Never run, and never will be. No credential is stored, shown or "
        "logged, and there is no setting to change that."
    ),
}


def covered() -> set[str]:
    """The base commands the matrix has rows for."""
    return {row.command.split()[0] for row in MATRIX}


def as_markdown() -> str:
    """The matrix as a table, for `infra-test/README.md`."""
    lines = [
        "| Command | Invoked by | Fixture | Emulator service | Expected | Verified by |",
        "|---|---|---|---|---|---|",
    ]
    for row in MATRIX:
        lines.append(
            f"| `{row.command}` | `{row.invoked_by}` | {row.fixture} | {row.service} "
            f"| {row.expects} | {row.verified_by} |"
        )
    return "\n".join(lines)
