"""One entry, and the Terraform file it is written in."""

from __future__ import annotations

from pathlib import Path

from backsight.engine.library.entry import (
    Broken,
    Entry,
    Kind,
    Source,
    file_name,
    parse,
    write,
)

A_SNIPPET = """# name: Private bucket
# kind: recipe
# resource: aws_s3_bucket
# tags: s3, storage, encryption
# about: A bucket nothing outside the account can reach, with encryption
#        and a log target.

resource "aws_s3_bucket" "${1:name}" {
  bucket = "${2:acme}-${var.environment}"
}
"""


def test_it_reads_the_header_and_keeps_the_body_as_terraform():
    found = parse(A_SNIPPET, path=Path("x.tf"))
    assert isinstance(found, Entry)
    assert found.name == "Private bucket"
    assert found.kind is Kind.RECIPE
    assert found.resource == "aws_s3_bucket"
    assert found.tags == ("s3", "storage", "encryption")
    assert found.body.startswith('resource "aws_s3_bucket"')
    assert "${var.environment}" in found.body


def test_prose_wraps_across_continuation_lines():
    found = parse(A_SNIPPET)
    assert found.about == (
        "A bucket nothing outside the account can reach, with encryption and a log target."
    )


def test_a_file_with_no_name_is_reported_rather_than_skipped():
    """A snippet somebody wrote that silently never appears is worse than one
    that appears with a complaint attached."""
    found = parse('resource "aws_s3_bucket" "x" {}\n', path=Path("x.tf"))
    assert isinstance(found, Broken)
    assert "no `# name:`" in found.why


def test_a_kind_nobody_recognises_is_reported_with_the_alternatives():
    found = parse("# name: X\n# kind: thingummy\n\nx\n")
    assert isinstance(found, Broken)
    assert "snippet" in found.why and "runbook" in found.why


def test_a_comment_that_is_not_a_header_is_left_in_the_body():
    found = parse('# name: X\n\n# why this exists\nresource "a" "b" {}\n')
    assert "# why this exists" in found.body


def test_a_plain_terraform_file_is_not_mistaken_for_an_entry():
    assert isinstance(parse('# a note about this module\nresource "a" "b" {}\n'), Broken)


def test_it_round_trips_through_the_file_it_writes():
    first = parse(A_SNIPPET)
    again = parse(write(first))
    assert again.name == first.name
    assert again.kind is first.kind
    assert again.tags == first.tags
    assert again.about == first.about
    assert again.body == first.body
    assert again.resource == first.resource


def test_searching_reaches_everything_a_person_might_remember():
    found = parse(A_SNIPPET)
    for term in ("private", "s3", "encryption", "aws_s3_bucket", "bucket ="):
        assert found.matches(term), term
    assert not found.matches("lambda")


def test_every_word_has_to_match_rather_than_any():
    found = parse(A_SNIPPET)
    assert found.matches("private bucket")
    assert not found.matches("private lambda")


def test_an_empty_term_matches_everything():
    assert parse(A_SNIPPET).matches("   ")


A_RUNBOOK = """# name: Rotate the database password
# kind: runbook
# about: Three steps, in this order.

# step: Take a snapshot first
# run: tofu apply -target=aws_db_snapshot.before_rotation
resource "aws_db_snapshot" "before_rotation" {
  db_instance_identifier = aws_db_instance.main.id
}

# step: Change the password
Set the new value in your secret store, then plan.

# step: Confirm nothing else moved
# run: tofu plan -refresh-only
"""


def test_a_runbook_reads_as_ordered_steps():
    found = parse(A_RUNBOOK)
    assert found.is_a_runbook
    assert [step.title for step in found.steps] == [
        "Take a snapshot first",
        "Change the password",
        "Confirm nothing else moved",
    ]


def test_a_step_carries_its_command_and_its_body_separately():
    steps = parse(A_RUNBOOK).steps
    assert steps[0].command == "tofu apply -target=aws_db_snapshot.before_rotation"
    assert 'resource "aws_db_snapshot"' in steps[0].body
    assert steps[0].is_a_command


def test_a_step_with_only_prose_is_still_a_step():
    steps = parse(A_RUNBOOK).steps
    assert not steps[1].is_a_command
    assert "secret store" in steps[1].body


def test_only_a_runbook_is_read_as_steps():
    assert parse(A_SNIPPET).steps == ()


def test_where_it_came_from_decides_whether_it_can_be_edited():
    assert Source.YOURS.is_editable
    assert Source.WORKSPACE.is_editable
    assert not Source.BUILT_IN.is_editable
    assert not Source.SHARED.is_editable


def test_a_file_name_is_something_findable_in_a_listing():
    assert file_name("Private bucket with access logs") == "private-bucket-with-access-logs.tf"
    assert file_name("  ***  ") == "entry.tf"


def test_each_kind_says_what_you_do_with_it():
    """They are not all "insert" — an example is a file, a runbook is read."""
    assert Kind.SNIPPET.what_it_does == "Insert"
    assert Kind.EXAMPLE.what_it_does == "Open as a new file"
    assert Kind.RUNBOOK.what_it_does == "Open"
