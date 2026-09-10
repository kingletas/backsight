"""Nothing the code or its tests need is hidden from git.

**A whole package was never committed.** The machine this is written on has a
user-level excludes file that ignores every directory called `sandbox/`, which
is the name of a package here — so four modules the application imports existed
on this disk and in no commit, every clone was missing them, and every check run
here passed because the files were sitting beside the ones that were tracked.
The stack fixtures went the same way, under a rule meant for plan files.

A clone cannot see this failure: it has no ignored files to find. It is only
visible on the machine that has them, which is where this runs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# What these trees are allowed to hide: what a run writes, never what a person
# wrote.
GENERATED = ("__pycache__/", ".pyc", ".tfplan", "/.terraform/", ".pytest_cache/")


def _ignored(*trees: str) -> list[str]:
    found = subprocess.run(
        ["git", "ls-files", "--others", "--ignored", "--exclude-standard", "--", *trees],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    return [name for name in found if not any(part in name for part in GENERATED)]


def test_no_source_test_or_fixture_file_is_ignored():
    hidden = _ignored("src", "tests", "fixtures", "infra-test", "scripts", "docs")
    assert not hidden, (
        "these exist here and would be missing from every clone — find the rule with "
        "`git check-ignore -v <path>`:\n" + "\n".join(hidden)
    )
