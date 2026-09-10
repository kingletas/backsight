"""A file the user did not ask us to change comes back byte for byte.

FR-ED-07 and DD-9. The corpus is deliberately ugly: `tofu fmt` would rewrite six
of these files, and doing that on somebody's behalf is what this test forbids.
"""

from pathlib import Path

import pytest

from backsight.engine.hcl.document import Document

ROOT = Path(__file__).resolve().parents[2]
CORPUS = sorted((ROOT / "fixtures" / "hcl" / "ugly").glob("*.tf"))


def test_the_corpus_is_present():
    assert len(CORPUS) >= 20, f"only {len(CORPUS)} corpus files; the plan asks for at least 20"


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_open_and_save_without_editing_changes_nothing(path: Path, tmp_path: Path):
    original = path.read_bytes()
    document = Document.read(path)
    out = tmp_path / path.name
    document.write(out)
    assert out.read_bytes() == original


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_the_corpus_itself_is_never_rewritten(path: Path):
    """The fixtures are the evidence. A test that tidies them destroys the evidence."""
    assert Document.read(path).data == path.read_bytes()
