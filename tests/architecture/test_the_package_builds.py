"""The wheel builds, and carries the data the app reads at run time.

`pyproject.toml` force-included `src/backsight/app/schemes`, which has never
existed — the editor schemes live under `app/theme/schemes`. The build failed
outright, and nothing here ran a build, so it went unnoticed until a dependency
was added. Correcting the path then made the build fail a second way, by adding
every scheme to the archive twice: they are inside the package already.
"""

from __future__ import annotations

import tomllib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_the_schemes_are_inside_the_packaged_tree():
    """The cheap half. `packages` carries them; nothing else needs to."""
    stored = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = stored["tool"]["hatch"]["build"]["targets"]["wheel"]
    packaged = wheel["packages"]
    schemes = ROOT / "src" / "backsight" / "app" / "theme" / "schemes"
    assert list(schemes.glob("*.xml")), "there are no schemes to package"
    assert any(str(schemes).startswith(str(ROOT / where)) for where in packaged)


def test_nothing_is_force_included_twice():
    """Force-including a path already inside `packages` fails the build."""
    stored = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    wheel = stored["tool"]["hatch"]["build"]["targets"]["wheel"]
    for source in wheel.get("force-include", {}):
        assert not any(
            str((ROOT / source).resolve()).startswith(str((ROOT / where).resolve()))
            for where in wheel["packages"]
        ), f"{source} is inside a packaged tree and would be added twice"


@pytest.mark.sandbox
def test_the_wheel_carries_the_editor_schemes(tmp_path: Path):
    import subprocess

    subprocess.run(  # noqa: S603
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],  # noqa: S607
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    wheel = next(tmp_path.glob("*.whl"))
    inside = zipfile.ZipFile(wheel).namelist()
    assert [n for n in inside if n.endswith("backsight-light.xml")]
    assert [n for n in inside if n.endswith("backsight-dark.xml")]


def test_the_shipped_library_is_inside_the_packaged_tree():
    """It is data the application reads at run time, like the editor schemes.
    A wheel without it installs a library that is empty on every machine but
    this one — and the schemes taught this lesson once already."""
    stored = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    packaged = stored["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    shipped = ROOT / "src" / "backsight" / "engine" / "library" / "shipped"
    assert list(shipped.glob("*.tf")), "there is no shipped library to package"
    assert any(str(shipped).startswith(str(ROOT / where)) for where in packaged)


def test_the_built_wheel_actually_carries_the_shipped_library():
    """The cheap check above says the path is inside a packaged tree. Hatch
    excludes by pattern, and `.tf` is not a file type any default includes."""
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as scratch:
        built = subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", scratch],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        assert built.returncode == 0, built.stderr
        wheel = next(Path(scratch).glob("*.whl"))
        with zipfile.ZipFile(wheel) as archive:
            carried = [n for n in archive.namelist() if "/library/shipped/" in n]
        assert carried, "the wheel carries no shipped library"
        assert any(name.endswith("moved-block.tf") for name in carried)
