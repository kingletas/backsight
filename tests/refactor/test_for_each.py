"""count to for_each: every instance keeps its identity, or the change is refused."""

import pytest
from corpus import cases

from backsight.engine.refactor.for_each import Conversion, moved_blocks, pairs

THREE = Conversion(resource_type="terraform_data", name="n", keys=("a", "b", "c"))


def test_every_index_is_mapped_to_its_key():
    assert pairs(THREE) == [
        ("terraform_data.n[0]", 'terraform_data.n["a"]'),
        ("terraform_data.n[1]", 'terraform_data.n["b"]'),
        ("terraform_data.n[2]", 'terraform_data.n["c"]'),
    ]


def test_the_blocks_are_written_so_they_can_be_read():
    written = moved_blocks(THREE)
    assert written.count("moved {") == 3
    assert "from = terraform_data.n[0]" in written
    assert 'to   = terraform_data.n["a"]' in written


def test_a_conversion_with_no_keys_is_refused():
    with pytest.raises(ValueError, match="needs the keys"):
        Conversion("terraform_data", "n", ())


def test_two_instances_becoming_one_key_is_refused():
    """One of them would be destroyed. Refuse before a plan has to say so."""
    with pytest.raises(ValueError, match="cannot become the same key"):
        Conversion("terraform_data", "n", ("a", "a"))


def test_an_empty_key_is_refused():
    with pytest.raises(ValueError, match="empty key"):
        Conversion("terraform_data", "n", ("a", ""))


def test_a_data_source_keeps_its_prefix():
    conversion = Conversion("aws_ami", "n", ("a",), kind="data")
    assert conversion.old_address(0) == "data.aws_ami.n[0]"


def test_the_generated_blocks_match_the_corpus_case():
    """The corpus case was verified by a real plan; this must produce the same."""
    case = next(c for c in cases() if c.name == "count-to-for-each")
    assert pairs(THREE) == [(f, t) for f, t in case.moved]
