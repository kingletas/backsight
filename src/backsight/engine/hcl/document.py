"""A file on disk, held so that giving it back unchanged is the easy path.

FR-ED-07 and DD-9: Backsight never reformats, reorders or rewrites a file the
user did not ask it to. The bytes are kept, not a re-rendered parse of them, so
an untouched document is byte-identical by construction rather than by care.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


class NotUtf8(Exception):
    """A file whose bytes are not UTF-8, so it cannot be shown without damage.

    Both ways of forcing it are worse than refusing. A reversible decode produces
    lone surrogates, which the text buffer will not hold; a lossy one is accepted
    and then saves different bytes than it opened, which is the file corruption
    round-trip safety exists to prevent.
    """

    def __init__(self, path: Path, position: int) -> None:
        # The file's name, not its path. A message a person reads names the file
        # they clicked on, and a message that reaches a screenshot or a log
        # should not carry somebody's home directory with it.
        super().__init__(
            f"{path.name} is not UTF-8 — byte {position} cannot be read. "
            "Convert the file to UTF-8 and open it again."
        )
        self.path = path
        self.position = position


@dataclass(frozen=True)
class Document:
    """The exact bytes of one file, and where they came from."""

    path: Path
    data: bytes

    @classmethod
    def read(cls, path: Path) -> Document:
        return cls(path=path, data=Path(path).read_bytes())

    def write(self, path: Path | None = None) -> None:
        """Replaces the file in one step, so no reader ever sees half of it.

        A plain write truncates and then fills, and everything in this
        application reads these files while they are being edited — the source
        map, the palette, the gutter, the change map. A reader landing in that
        window sees an empty file and reports a workspace with no resources in
        it. A crash there leaves the person's own source truncated, which is
        worse.

        The temporary file goes in the same directory, because `os.replace` is
        only atomic within one filesystem.
        """
        target = Path(path or self.path)
        handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.")
        try:
            with os.fdopen(handle, "wb") as writing:
                writing.write(self.data)
                writing.flush()
                # The rename is atomic; the content reaching the disk is not.
                os.fsync(writing.fileno())
            if target.exists():
                # A new file gets the process default; an existing one keeps
                # whatever it had, which may be deliberate.
                os.chmod(temporary, target.stat().st_mode & 0o7777)
            os.replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    @property
    def text(self) -> str:
        """The content as text, for anything that reads it rather than keeps it.

        Refuses rather than mangling. Terraform's own files are UTF-8, so a file
        that is not is broken input, and the useful thing is to say which byte.
        """
        try:
            return self.data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise NotUtf8(self.path, error.start) from error

    @property
    def is_utf8(self) -> bool:
        try:
            self.data.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return True
