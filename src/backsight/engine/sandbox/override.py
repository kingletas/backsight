"""Pointing the provider at the emulator, without touching anything the user wrote.

FR-SIM-02. Terraform merges `*_override.tf` over the rest of a configuration, so
the redirection is a file that is added rather than an edit to a file that
exists. And the whole thing runs in a copy of the workspace, so a user file
cannot be changed even by accident — DD-9 holds by construction here rather than
by care.

**Every endpoint the provider declares is redirected, not only the ones the
emulator has.** A service left pointing at the real endpoint would reach a real
account with the dummy credentials attached, and the failure would look like a
permissions problem rather than what it is.
"""

from __future__ import annotations

import shutil
from pathlib import Path

# Written into the copy, never into the user's directory. The `_override` suffix
# is what makes Terraform merge it rather than treat it as a second provider.
OVERRIDE_FILE = "backsight_sandbox_override.tf"

# The emulator accepts any credentials. These are the ones its own documentation
# uses, and they are not a secret in any sense.
DUMMY_KEY = "test"

CARRIED = (".terraform", ".terraform.lock.hcl")


def override_hcl(endpoint: str, services: list[str], region: str = "us-east-1") -> str:
    """The provider override, generated rather than kept as a template."""
    if not services:
        raise ValueError("an override with no endpoints would reach the real cloud")
    lines = [
        "# Written by Backsight for a convergence run. Not part of your configuration,",
        "# and never written into your workspace — this file lives in a copy.",
        "",
        'provider "aws" {',
        f'  region                      = "{region}"',
        f'  access_key                  = "{DUMMY_KEY}"',
        f'  secret_key                  = "{DUMMY_KEY}"',
        "  s3_use_path_style           = true",
        "  skip_credentials_validation = true",
        "  skip_metadata_api_check     = true",
        "  skip_region_validation      = true",
        "  skip_requesting_account_id  = true",
        "",
        "  endpoints {",
    ]
    width = max(len(name) for name in services)
    lines += [f'    {name.ljust(width)} = "{endpoint}"' for name in sorted(services)]
    lines += ["  }", "}", ""]
    return "\n".join(lines)


def services_from_schema(index) -> list[str]:
    """Every service the pinned provider has an endpoint for.

    Read from the schema rather than listed here, so a provider upgrade that adds
    a service does not quietly leave it pointing at the real cloud.
    """
    # Each service is an *attribute* of the endpoints block, not a block of its own.
    return sorted(
        attribute.name for attribute in index.attributes("aws", kind="provider", path="endpoints")
    )


def prepare(workspace: Path, scratch: Path, *, endpoint: str, services: list[str]) -> Path:
    """Copies the workspace and adds the override to the copy."""
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    for path in Path(workspace).rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(workspace)
        first = relative.parts[0] if relative.parts else ""
        if first.startswith(".") and first not in CARRIED:
            continue
        target = scratch / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    (scratch / OVERRIDE_FILE).write_text(override_hcl(endpoint, services), encoding="utf-8")
    return scratch
