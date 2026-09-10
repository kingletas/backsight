"""What this machine can authenticate as, and what it must never hand back.

Every profile here is invented. The one thing this layer promises is that no
value which could be a secret leaves it, so most of these check the promise
rather than the feature.
"""

from __future__ import annotations

import pytest

from backsight.engine.credentials.profiles import (
    SECRET_KEYS,
    Available,
    Kind,
    read,
)

# Every value here is invented, and the account is a word rather than twelve
# digits: the privacy gate refuses an ARN carrying an account number and cannot
# tell an invented one from a real one, which is the right stance for it.
A_CONFIG = """
[default]
region = us-east-1
output = json

[profile invented-prod]
sso_session = invented
sso_account_id = ACCOUNT
sso_role_name = ReadOnly
region = us-west-2

[profile invented-deploy]
role_arn = arn:aws:iam::ACCOUNT:role/InventedDeploy
source_profile = invented-prod
region = us-east-1

[profile invented-legacy]
region = eu-west-1

[profile invented-helper]
credential_process = /usr/bin/invented-helper

[sso-session invented]
sso_start_url = https://invented.awsapps.com/start
sso_region = us-east-1
"""

# Joined rather than written out. The fixture is the same either way, and a
# complete AKIA-shaped token on a source line is what every secret scanner is
# built to find — including the one GitHub runs on a push, which would refuse
# it and does not read anybody's allowlist comment.
A_KEY_ID = "AKIA" + "INVENTEDNOTREAL0"
A_SECRET = "wJalrXUtnFEMI" + "-invented-not-real-key"

A_CREDENTIALS = f"""
[invented-legacy]
aws_access_key_id = {A_KEY_ID}
aws_secret_access_key = {A_SECRET}
"""


@pytest.fixture
def machine(tmp_path):
    config = tmp_path / "config"
    credentials = tmp_path / "credentials"
    config.write_text(A_CONFIG, encoding="utf-8")
    credentials.write_text(A_CREDENTIALS, encoding="utf-8")
    return config, credentials


def found(machine, environ=None) -> Available:
    config, credentials = machine
    return read(config=config, credentials=credentials, environ=environ or {})


def test_it_finds_every_profile(machine):
    names = [profile.name for profile in found(machine).profiles]
    assert names == [
        "default",
        "invented-deploy",
        "invented-helper",
        "invented-legacy",
        "invented-prod",
    ]


def test_the_profile_prefix_is_the_file_format_not_the_name(machine):
    """`[profile x]` in config and `[x]` in credentials are the same profile."""
    assert found(machine).named("invented-prod") is not None
    assert found(machine).named("profile invented-prod") is None


def test_an_sso_session_is_not_a_profile(machine):
    assert found(machine).named("invented") is None


def test_each_one_is_classified_by_how_it_authenticates(machine):
    kinds = {profile.name: profile.kind for profile in found(machine).profiles}
    assert kinds["invented-prod"] is Kind.SSO
    assert kinds["invented-deploy"] is Kind.ROLE
    assert kinds["invented-legacy"] is Kind.STATIC
    assert kinds["invented-helper"] is Kind.PROCESS
    assert kinds["default"] is Kind.UNKNOWN


def test_keys_on_disk_are_named_as_the_thing_they_are(machine):
    """A key on disk is a key somebody can copy, and saying so is all this
    application can do about it."""
    assert Kind.STATIC.is_long_lived
    assert not Kind.SSO.is_long_lived
    assert not Kind.ROLE.is_long_lived


# --- the promise -----------------------------------------------------------


def test_no_secret_value_is_ever_returned(machine):
    """The one thing this layer exists to guarantee. What it never holds it
    cannot leak into a screenshot, a log line or a crash report."""
    everything = repr(found(machine))
    assert "AKIA" not in everything
    assert "wJalrXUtnFEMI" not in everything
    for key in SECRET_KEYS:
        assert key not in everything


def test_the_account_is_only_reported_where_the_file_says_it_outright(machine):
    """Never derived from an ARN, never guessed."""
    profiles = {one.name: one for one in found(machine).profiles}
    assert profiles["invented-prod"].account == "ACCOUNT"
    assert profiles["invented-deploy"].account == ""


def test_a_role_arn_gives_up_its_name_and_not_its_account(machine):
    deploy = found(machine).named("invented-deploy")
    assert deploy.role == "InventedDeploy"
    assert "ACCOUNT" not in deploy.role


# --- what is there at all --------------------------------------------------


def test_a_machine_with_nothing_says_so_rather_than_looking_broken(tmp_path):
    nothing = read(config=tmp_path / "no", credentials=tmp_path / "no", environ={})
    assert not nothing.any
    assert nothing.summary == "No AWS profiles found, and none in the environment"


def test_credentials_in_the_environment_count(machine):
    assert found(machine, {"AWS_ACCESS_KEY_ID": "AKIAINVENTED"}).from_environment
    assert not found(machine).from_environment


def test_a_named_profile_in_the_environment_counts_too(machine):
    assert found(machine, {"AWS_PROFILE": "invented-prod"}).from_environment


def test_a_config_that_will_not_parse_says_so_rather_than_finding_nothing(tmp_path):
    """An AWS config is one file, and a broken one is a broken one."""
    broken = tmp_path / "config"
    broken.write_text("[unclosed\nregion = x\n", encoding="utf-8")
    answer = read(config=broken, credentials=tmp_path / "no", environ={})
    assert not answer.any
    assert "could not be read" in answer.summary


def test_the_default_profile_is_findable_as_the_default(machine):
    assert found(machine).default.name == "default"


def test_the_summary_counts_what_is_there(machine):
    assert "5 profiles" in found(machine).summary
    assert "environment" in found(machine, {"AWS_ACCESS_KEY_ID": "x"}).summary


# --- which profile does what ------------------------------------------------


def a_pairing(machine, preferred=""):
    from backsight.engine.credentials.roles import choose

    return choose(found(machine), preferred=preferred)


def test_with_one_profile_both_operations_use_it_and_say_so(tmp_path):
    from backsight.engine.credentials.roles import choose

    config = tmp_path / "config"
    config.write_text("[profile only]\nregion = us-east-1\n", encoding="utf-8")
    pairing = choose(read(config=config, credentials=tmp_path / "no", environ={}))
    assert not pairing.is_split
    assert pairing.summary == "only for everything"
    assert pairing.reading.why == "the only one there is"


def test_a_profile_that_names_itself_read_only_is_used_for_reading(tmp_path):
    from backsight.engine.credentials.roles import choose

    config = tmp_path / "config"
    config.write_text(
        "[default]\nregion = us-east-1\n\n[profile invented-readonly]\nregion = us-east-1\n",
        encoding="utf-8",
    )
    pairing = choose(read(config=config, credentials=tmp_path / "no", environ={}))
    assert pairing.is_split
    assert pairing.reading.profile.name == "invented-readonly"
    assert pairing.changing.profile.name == "default"
    assert "read to" in pairing.summary or "to read" in pairing.summary


def test_naming_one_wins_over_the_guess(machine):
    """Somebody who chose is not asked to argue with a heuristic."""
    pairing = a_pairing(machine, preferred="invented-deploy")
    assert not pairing.is_split
    assert pairing.reading.profile.name == "invented-deploy"
    assert pairing.reading.why == "you chose it"


def test_no_profiles_at_all_chooses_nothing_rather_than_something(tmp_path):
    from backsight.engine.credentials.roles import choose

    pairing = choose(read(config=tmp_path / "no", credentials=tmp_path / "no", environ={}))
    assert not pairing.changing.is_chosen
    assert pairing.summary == "Nothing to apply with"
    assert pairing.reading.why == "there are no profiles"


def test_credentials_in_the_environment_are_said_rather_than_named(tmp_path):
    from backsight.engine.credentials.roles import choose

    pairing = choose(
        read(
            config=tmp_path / "no", credentials=tmp_path / "no", environ={"AWS_ACCESS_KEY_ID": "x"}
        )
    )
    assert pairing.reading.why == "credentials are in the environment"


# --- the activity log -------------------------------------------------------

from backsight.engine.credentials import activity  # noqa: E402


def test_what_happened_is_kept_and_read_back(tmp_path):
    activity.record(
        activity.Happened(what=activity.What.PLANNED, workspace="/x/prod", detail="4 changes"),
        home=tmp_path,
    )
    activity.record(
        activity.Happened(what=activity.What.APPLIED, workspace="/x/prod", outcome="ok"),
        home=tmp_path,
    )
    found_log = activity.read(home=tmp_path)
    assert [one.what for one in found_log] == [activity.What.PLANNED, activity.What.APPLIED]
    assert found_log[0].detail == "4 changes"


def test_a_line_reads_as_something_a_person_would_scan(tmp_path):

    said = activity.Happened(
        what=activity.What.APPLIED,
        workspace="/x/prod",
        detail="4 changes",
        at="2026-09-08T10:00:00+00:00",
    ).line
    assert "2026-09-08 10:00:00" in said
    assert "applied" in said
    assert "prod" in said


def test_an_unreadable_line_is_skipped_rather_than_losing_the_log(tmp_path):
    activity.record(activity.Happened(what=activity.What.PLANNED), home=tmp_path)
    with (activity.directory(tmp_path) / activity.FILE).open("a", encoding="utf-8") as handle:
        handle.write("not json\n")
    activity.record(activity.Happened(what=activity.What.APPLIED), home=tmp_path)
    assert len(activity.read(home=tmp_path)) == 2


def test_nothing_recorded_yet_is_an_empty_log_rather_than_an_error(tmp_path):

    assert activity.read(home=tmp_path) == []


def test_a_log_that_cannot_be_written_never_fails_the_work(tmp_path):
    """Losing a log line must never lose an apply."""
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    activity.record(activity.Happened(what=activity.What.APPLIED), home=blocked)


def test_it_exports_as_lines_a_person_reads(tmp_path):
    said = activity.as_text(
        [activity.Happened(what=activity.What.PLANNED, at="2026-09-08T10:00:00+00:00")]
    )
    assert said.endswith("\n")
    assert "planned" in said


def test_forgetting_it_is_possible_because_it_is_somebody_own_record(tmp_path):
    activity.record(activity.Happened(what=activity.What.PLANNED), home=tmp_path)
    activity.forget(home=tmp_path)
    assert activity.read(home=tmp_path) == []
