"""What a policy scan says, read from real checkov output.

Two captures, because the two shapes are not the same shape with a different
count: a run with findings is a list of check-type blocks and a run with none is
a single object. A reader written against one silently finds nothing for the
other.
"""

from __future__ import annotations

from pathlib import Path

from backsight.engine.policy.findings import (
    Report,
    Severity,
    read_checkov,
    suppressed,
)

FIXTURES = Path(__file__).resolve().parents[1].parent / "fixtures" / "policy"
FOUND = (FIXTURES / "checkov-findings.json").read_text(encoding="utf-8")
CLEAN = (FIXTURES / "checkov-clean.json").read_text(encoding="utf-8")


def test_it_reads_a_run_that_found_things():
    report = read_checkov(FOUND)
    assert report.ran
    assert report.count == 10
    assert not report.is_clean


def test_it_reads_a_run_that_found_nothing():
    """The shape is different, not the count — this is the whole reason for a
    second capture."""
    report = read_checkov(CLEAN)
    assert report.ran
    assert report.is_clean
    assert report.headline == "Nothing found by the policies that ran"


def test_every_finding_knows_where_it_is():
    """The difference between something the gutter can point at and a line in
    a report nobody opens."""
    for finding in read_checkov(FOUND).findings:
        assert finding.path
        assert finding.line > 0


def test_a_finding_names_the_resource_and_the_rule():
    report = read_checkov(FOUND)
    one = next(f for f in report.findings if f.rule == "CKV_AWS_24")
    assert one.resource == "aws_security_group.invented"
    # The rule is about ingress from anywhere; the address is in its title,
    # not a binding.
    assert "ingress from" in one.title
    assert one.summary.startswith("aws_security_group.invented — ")


def test_findings_can_be_asked_for_by_file():
    report = read_checkov(FOUND)
    assert report.at(Path("main.tf"))
    assert report.at(Path("nothing.tf")) == []


def test_an_unrated_severity_is_said_rather_than_guessed():
    """Checkov's community rules carry no severity, and inventing one would be
    this application deciding how much somebody should care."""
    report = read_checkov(FOUND)
    assert Severity.UNKNOWN in report.by_severity


def test_output_that_will_not_parse_is_a_failure_rather_than_a_clean_run():
    """The worst answer a checker can give."""
    report = read_checkov("not json at all")
    assert not report.is_clean
    assert not report.ran
    assert "nothing readable" in report.failure


def test_a_scanner_that_is_not_installed_is_a_state_rather_than_a_failure():
    report = Report()
    assert not report.ran
    assert "Install checkov" in report.headline


def test_it_never_claims_to_have_stopped_anything():
    """Severity drives presentation, not enforcement — a desktop application
    cannot stop somebody running apply in a terminal."""
    for text in (FOUND, CLEAN):
        said = read_checkov(text).headline.lower()
        assert "blocked" not in said
        assert "prevented" not in said


def test_a_suppressed_rule_is_gone_and_the_rest_stay():
    report = read_checkov(FOUND)
    left = suppressed(report.findings, ["CKV_AWS_24"])
    assert len(left) == report.count - 1
    assert all(one.rule != "CKV_AWS_24" for one in left)


def test_suppressing_nothing_changes_nothing():
    report = read_checkov(FOUND)
    assert len(suppressed(report.findings, ["", "  "])) == report.count
