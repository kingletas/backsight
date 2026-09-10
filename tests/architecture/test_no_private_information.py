"""Nothing in this repository names the machine it was written on.

This is meant to be published, and what leaks into a repository is not what a
reader would think to look for: a home path in a docstring, a real account
number in a fixture, the author's own login in a test.

The username and hostname are read at run time rather than written down. A test
that hardcoded them would be the leak it exists to prevent.
"""

from __future__ import annotations

import getpass
import re
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Binary and generated files: a gzipped schema is not text and a PNG is not either.
SKIP_SUFFIXES = {".png", ".jpg", ".svg", ".zip", ".gz", ".lock"}

# Published on purpose: the home path the documentation uses, the address in the
# licence and package metadata, and the domain the application id is built from.
# The domain is here because a short login is a substring of it, which is the
# shape of false positive this check will keep producing.
ALLOWED = ("/home/you", "code@kingletas.com", "kingletas")

# A login shorter than this is a substring of ordinary English.
SHORTEST_CHECKABLE = 4

# Logins that belong to a machine rather than a person — a container runs as
# root and a CI runner as runner, and both are ordinary words in these files.
# Nobody's identity can leak through them, so they are not looked for.
NOBODY = {"root", "runner", "ubuntu", "ci", "build"}

# A twelve-digit AWS account number, and the ARNs that carry one. Fixtures are
# invented; a real one arriving here is the failure this catches.
ACCOUNT_NUMBER = re.compile(r"(?<!\d)\d{12}(?!\d)")
ARN_WITH_ACCOUNT = re.compile(r"arn:aws[a-z-]*:[a-z0-9-]+:[a-z0-9-]*:(\d{12}):")

# Accounts that are invented on sight: ten leading zeros, or the one AWS's own
# documentation uses. A fixture needs an account to look like a stack, and one
# of these can never be mistaken for somebody's.
INVENTED_ACCOUNT = re.compile(r"^(?:0{10}\d{2}|123456789012)$")


def tracked_text_files() -> list[Path]:
    """Every tracked text file but this one.

    A scanner that scans itself matches its own patterns and reports them as
    findings. This file carries the patterns and no private information.
    """
    # Tracked *and* not-yet-added files. `git ls-files` alone cannot see a file
    # being committed for the first time, so a leak in a new file would only be
    # caught by the run after the one that let it in.
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    here = Path(__file__).resolve()
    files = []
    for name in listed.stdout.split("\0"):
        if not name:
            continue
        path = ROOT / name
        if path.suffix in SKIP_SUFFIXES or not path.is_file() or path.resolve() == here:
            continue
        files.append(path)
    return files


def contents() -> list[tuple[Path, str]]:
    out = []
    for path in tracked_text_files():
        try:
            out.append((path, path.read_text(encoding="utf-8")))
        except UnicodeDecodeError:
            continue
    return out


def test_no_file_names_this_machine():
    login, host = getpass.getuser(), socket.gethostname()
    wanted = [host] + ([] if login in NOBODY else [login, f"/home/{login}"])
    needles = [
        re.compile(rf"(?<![\w-]){re.escape(n)}(?![\w-])")
        for n in wanted
        if len(n) >= SHORTEST_CHECKABLE
    ]
    for path, text in contents():
        for needle in needles:
            for line in text.splitlines():
                if needle.search(line) and not any(a in line for a in ALLOWED):
                    raise AssertionError(f"{path.relative_to(ROOT)} names this machine")


# A per-user scratch directory such as /tmp/name-1000/ names the account that
# captured a fixture, whatever the login happens to be on the machine running this.
PER_USER_TEMP = re.compile(r"/(?:tmp|var/tmp)/[A-Za-z][\w.]*-\d{3,}/")


def test_no_file_carries_a_per_user_temp_path():
    for path, text in contents():
        found = PER_USER_TEMP.search(text)
        assert found is None, f"{path.relative_to(ROOT)} carries {found.group(0)}"


def test_no_file_carries_an_account_number():
    for path, text in contents():
        for found in ARN_WITH_ACCOUNT.finditer(text):
            assert INVENTED_ACCOUNT.match(found.group(1)), (
                f"{path.relative_to(ROOT)} carries an ARN with an account number"
            )
        for line in text.splitlines():
            # A plan fixture is full of long numbers; only bare twelve-digit runs
            # in something that reads like an identifier are worth failing on.
            if "account" not in line.lower():
                continue
            for number in ACCOUNT_NUMBER.findall(line):
                if not INVENTED_ACCOUNT.match(number):
                    raise AssertionError(f"{path.relative_to(ROOT)}: {line.strip()[:70]}")


def test_an_invented_account_is_told_apart_from_a_real_one():
    """The allowance is narrow, or it is the leak with a permit."""
    assert INVENTED_ACCOUNT.match("000000000001")
    assert INVENTED_ACCOUNT.match("123456789012")
    assert not INVENTED_ACCOUNT.match("555000111222")
    assert not INVENTED_ACCOUNT.match("100000000001")


# Credential shapes that are unambiguous on sight. Secret scanners commonly skip
# fixture directories, so this test is what looks at them, and it runs in CI.
CREDENTIALS = {
    "an AWS access key id": re.compile(r"(?<![A-Z0-9])(AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"),
    "a private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "a GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "an AWS secret key": re.compile(
        r"(?i)aws_secret_access_key\s*[=:]\s*[\"']?[A-Za-z0-9/+]{40}(?![A-Za-z0-9/+])"
    ),
}


def test_no_file_carries_a_credential():
    found = [
        f"{path.relative_to(ROOT)}: {what}"
        for path, said in contents()
        for what, shape in CREDENTIALS.items()
        if shape.search(said)
    ]
    assert not found, "\n".join(found)


def test_the_credential_shapes_recognise_what_they_are_for():
    """A pattern that matches nothing reads as a clean repository."""
    samples = {
        "an AWS access key id": "AKIA" + "ABCDEFGHIJKLMNOP",
        "a private key": "-----BEGIN RSA " + "PRIVATE KEY-----",
        "a GitHub token": "ghp_" + "a" * 36,
        "an AWS secret key": "aws_secret_access_key = " + "a" * 40,
    }
    for what, sample in samples.items():
        assert CREDENTIALS[what].search(sample), what
    # The emulator's own test credentials are not a credential.
    assert not any(shape.search('access_key = "test"') for shape in CREDENTIALS.values())


# --- what the published tree must not carry about how it was made ------------

# Instructions written for coding agents working on this checkout. They describe
# a private working setup, and they stay on the machine that has one.
AGENT_FILES = {
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".cursorrules",
    ".github/copilot-instructions.md",
}

# A folder in a numbered notes tree, like `07 Archive/`. The shape is generic;
# the actual names are private and are not written down here.
NOTES_PATH = re.compile(r"(?<![\w/.])\d\d [A-Z][a-z]+/")

# Names this tree must never mention — the author's own tools, folders and
# projects — kept in an untracked file on the machine that has them. Writing
# them into this test would publish the list it exists to protect, so a clone
# has no such file and skips the check.
PRIVATE_NAMES = ROOT / "local.d" / "private-names.txt"


def _private_names() -> list[str]:
    if not PRIVATE_NAMES.exists():
        return []
    lines = PRIVATE_NAMES.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


# A person narrated in the third person. This project's documents describe the
# software; nobody working on it is a character in them.
NARRATION = re.compile(r"\b(?:he|him|his|she|her|hers)\b", re.IGNORECASE)
PROSE = {".md", ".py", ".toml", ".yml", ".sh"}


def _tracked() -> set[str]:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(listed.stdout.splitlines())


def test_no_agent_working_file_is_published():
    found = sorted(AGENT_FILES & _tracked())
    assert not found, f"agent working files are tracked: {found} — they belong in local.d/"


def test_no_file_points_into_private_notes():
    for path, text in contents():
        found = NOTES_PATH.search(text)
        where = path.relative_to(ROOT)
        assert found is None, f"{where} points into private notes: {found.group(0)}"


@pytest.mark.skipif(not PRIVATE_NAMES.exists(), reason="no private-names list on this machine")
def test_no_file_names_anything_private():
    names = _private_names()
    for path, text in contents():
        for name in names:
            assert name not in text, f"{path.relative_to(ROOT)} names something private"


def test_no_document_narrates_a_person():
    for path, text in contents():
        if path.suffix not in PROSE or "fixtures" in path.relative_to(ROOT).parts:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            found = NARRATION.search(line)
            assert found is None, (
                f"{path.relative_to(ROOT)}:{number} narrates a person: {line.strip()[:70]}"
            )


def test_the_new_patterns_recognise_what_they_are_for():
    """A pattern that matches nothing reads as a clean tree."""
    assert NOTES_PATH.search("filed under 07 Archive/old")
    assert not NOTES_PATH.search("version 1.12 Released/")
    assert NARRATION.search("She was typing while the build ran")
    assert not NARRATION.search("the shell, the theme, other")
