"""Which profiles exist, and what kind each one is. Never what is in them.

`~/.aws/config` and `~/.aws/credentials` are INI files somebody else's tooling
owns. This reads the section names and the *shape* of each — whether it points
at an SSO session, assumes a role, carries static keys, or defers to the
instance it runs on — and stops there.

**No value that could be a secret is ever returned.** A key id is enough to
identify an account in a log; a secret key is enough to spend money. Neither
leaves this module, so neither can reach a screenshot, a log line, a crash
report or a commit. The rest of the application asks what is available and gets
a shape, which is all it needs to stop guessing.
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

CONFIG = Path("~/.aws/config")
CREDENTIALS = Path("~/.aws/credentials")

# Anything matching one of these is a secret. Named so the test that proves
# none of them is returned has something to check against.
SECRET_KEYS = frozenset(
    {
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "aws_security_token",
        "password",
        "secret",
        "token",
    }
)

# What the environment uses instead of a profile.
ENVIRONMENT_KEYS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE")


class Kind(Enum):
    """How a profile expects to authenticate."""

    SSO = "single sign-on"
    ROLE = "an assumed role"
    STATIC = "keys on disk"
    PROCESS = "a credential process"
    INSTANCE = "the instance it runs on"
    UNKNOWN = "not clear from the file"

    @property
    def is_long_lived(self) -> bool:
        """Whether it puts a credential on disk that does not expire.

        The one thing worth saying about a profile beyond its name: a key on
        disk is a key somebody can copy, and no amount of care here changes
        that. Saying so is all this application can do about it.
        """
        return self is Kind.STATIC


@dataclass(frozen=True)
class Profile:
    """One profile, by name and by shape."""

    name: str
    kind: Kind = Kind.UNKNOWN
    region: str = ""
    # The account, only when the file states it outright — an SSO profile does.
    # Never derived, never guessed.
    account: str = ""
    role: str = ""
    session: str = ""
    is_default: bool = False

    @property
    def summary(self) -> str:
        """One line, in the words somebody would use about their own setup."""
        said = [self.kind.value]
        if self.region:
            said.append(self.region)
        return " · ".join(said)


@dataclass(frozen=True)
class Available:
    """Everything this machine could authenticate as."""

    profiles: tuple[Profile, ...] = ()
    from_environment: bool = False
    unreadable: str = ""

    @property
    def any(self) -> bool:
        return bool(self.profiles) or self.from_environment

    @property
    def default(self) -> Profile | None:
        return next((one for one in self.profiles if one.is_default), None)

    def named(self, name: str) -> Profile | None:
        return next((one for one in self.profiles if one.name == name), None)

    @property
    def summary(self) -> str:
        if self.unreadable:
            return self.unreadable
        if not self.any:
            return "No AWS profiles found, and none in the environment"
        parts = []
        if self.profiles:
            count = len(self.profiles)
            parts.append(f"{count} profile{'' if count == 1 else 's'}")
        if self.from_environment:
            parts.append("credentials in the environment")
        return " · ".join(parts)


def _kind_of(values: dict[str, str]) -> Kind:
    """What a section's keys say about how it authenticates."""
    if "sso_session" in values or "sso_start_url" in values:
        return Kind.SSO
    if "role_arn" in values:
        return Kind.ROLE
    if "credential_process" in values:
        return Kind.PROCESS
    if "aws_access_key_id" in values:
        return Kind.STATIC
    if values.get("credential_source", "").strip():
        return Kind.INSTANCE
    return Kind.UNKNOWN


def _read(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    found = Path(path).expanduser()
    if found.is_file():
        # `read` swallows a parse error into an exception we want to see, and
        # ignores a missing file, which is the ordinary case.
        parser.read(found, encoding="utf-8")
    return parser


def read(*, config: Path = CONFIG, credentials: Path = CREDENTIALS, environ=None) -> Available:
    """Every profile this machine has, by name and shape.

    Returns nothing about what is in them. A profile that will not parse takes
    the whole file with it — an AWS config is one file and a broken one is a
    broken one — and that is said rather than silently returning nothing.
    """
    where = environ if environ is not None else os.environ
    try:
        settings = _read(config)
        keys = _read(credentials)
    except configparser.Error as refused:
        return Available(unreadable=f"Your AWS config could not be read: {refused}")

    found: dict[str, dict[str, str]] = {}
    for section in settings.sections():
        # `[profile name]` in config, `[name]` in credentials, and `[default]`
        # in either. The prefix is the file format's, not the profile's name.
        name = section[len("profile ") :] if section.startswith("profile ") else section
        if section.startswith("sso-session "):
            continue
        found.setdefault(name, {}).update(dict(settings[section]))
    for section in keys.sections():
        found.setdefault(section, {}).update(dict(keys[section]))

    profiles = tuple(
        Profile(
            name=name,
            kind=_kind_of(values),
            region=values.get("region", "").strip(),
            account=values.get("sso_account_id", "").strip(),
            role=values.get("sso_role_name", "").strip() or _role_name(values.get("role_arn", "")),
            session=values.get("sso_session", "").strip(),
            is_default=name == "default",
        )
        for name, values in sorted(found.items())
    )
    return Available(profiles=profiles, from_environment=_in_the_environment(where))


def _role_name(arn: str) -> str:
    """The role's name out of its ARN. The account in it is not returned."""
    said = arn.strip()
    return said.rsplit("/", 1)[-1] if "/" in said else ""


def _in_the_environment(where) -> bool:
    """Whether the environment carries credentials, without reading them."""
    return any(where.get(key) for key in ENVIRONMENT_KEYS)
