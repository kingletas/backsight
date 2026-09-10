"""A real window on a private display, and the helpers for asking what it shows.

The unit suite was 1,856 tests green while the editor drew nothing at all —
every component worked and the route to it did not. So these drive the window
the way a person does and ask what is **on screen**, which means two things a
unit test never checks: that a widget is visible, and that it has a size.

A widget can be visible, hold the right text, pass every assertion about its
state, and be zero pixels wide. That is what happened.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

gi = pytest.importorskip("gi", reason="the toolkit is not installed")

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"

# Big enough that nothing is squeezed out for want of room, which would make a
# layout failure look like a layout decision.
WIDE = 1280
TALL = 820


@pytest.fixture(scope="session", autouse=True)
def _own_display():
    """A display of our own, and a config of our own.

    Both matter. The smoke once ran against the developer's settings file and
    ten checks failed for a reason that was not in the repository.
    """
    import sys

    sys.path.insert(0, str(ROOT / "src"))
    from backsight.app.offscreen import use_a_private_display

    scratch = tempfile.mkdtemp(prefix="backsight-acceptance-")
    os.environ["XDG_CONFIG_HOME"] = str(Path(scratch) / "config")
    os.environ["XDG_STATE_HOME"] = str(Path(scratch) / "state")
    os.environ["XDG_DATA_HOME"] = str(Path(scratch) / "data")
    return use_a_private_display()


def pytest_collection_modifyitems(items):
    """Everything here is an acceptance test, so nothing has to remember to
    say so."""
    for item in items:
        item.add_marker(pytest.mark.acceptance)


@pytest.fixture
def window(_own_display):
    """A window that has actually been laid out."""
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from backsight.app.window import Window

    found = Window()
    found.set_default_size(WIDE, TALL)
    found.present()
    settle(found)
    yield found
    found.close()


from tests.acceptance.looking import settle  # noqa: E402


@pytest.fixture
def workspace(tmp_path):
    """A workspace that plans offline — no provider, no credentials, no network."""
    import shutil

    where = tmp_path / "plannable"
    shutil.copytree(FIXTURES / "plannable", where)
    return where


@pytest.fixture
def opened(window, workspace):
    """A window with that workspace open and its file in the editor."""
    window.open_workspace(workspace)
    settle(window)
    window.open_file(workspace / "main.tf")
    settle(window)
    return window
