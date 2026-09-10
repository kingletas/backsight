"""The command line, which today opens the window and nothing else."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backsight import __version__


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backsight",
        description="A Terraform workbench that shows what a change will do while you write it.",
    )
    parser.add_argument("--version", action="version", version=f"backsight {__version__}")
    parser.add_argument(
        "workspace",
        nargs="?",
        type=Path,
        help="a directory to open. Without one the window opens empty.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv if argv is not None else sys.argv[1:])
    if arguments.workspace is not None and not arguments.workspace.is_dir():
        print(f"{arguments.workspace} is not a directory", file=sys.stderr)
        return 2
    # Imported here so that `--version` and `--help` work on a machine with no
    # toolkit installed, which is also how the engine tests run.
    from backsight.app.application import Application

    return Application(workspace=arguments.workspace).run([])
