"""The two labels on a block header are different kinds of thing.

`resource "aws_instance" "api"` — the first is the provider's vocabulary and
the second is a name you chose, and telling them apart is most of what reading
HCL is. They were one colour.

**Changing the colour scheme did not fix it**, and that is the point of this
file. GtkSourceView's `terraform.lang` captures both quoted words in a single
`label` group, so no scheme can give them different colours — the fix has to
read the syntax tree, which is what every other question about HCL here already
does.
"""

from __future__ import annotations

from backsight.app.block_labels import spans


def kinds(source: str) -> list[tuple[str, str]]:
    """Each label and what it was taken to be."""
    said = source.encode("utf-8")
    lines = said.split(b"\n")
    found = []
    for row, start, end, _length, kind in spans(said):
        text = lines[row].decode("utf-8")
        found.append((text[start:end], kind))
    return found


def test_a_resource_has_a_type_and_a_name():
    assert kinds('resource "aws_instance" "api" {}') == [
        ('"aws_instance"', "type"),
        ('"api"', "name"),
    ]


def test_a_data_source_is_the_same_shape():
    assert kinds('data "aws_ami" "latest" {}') == [('"aws_ami"', "type"), ('"latest"', "name")]


def test_a_module_has_only_a_name():
    """`module "vpc"` names a thing you called `vpc`. Colouring that as
    provider vocabulary would be a confident lie about a very common line."""
    assert kinds('module "vpc" {}') == [('"vpc"', "name")]


def test_a_variable_has_only_a_name():
    assert kinds('variable "region" {}') == [('"region"', "name")]


def test_a_block_with_no_labels_has_nothing_to_colour():
    assert kinds("locals {}") == []
    assert kinds("terraform {}") == []


def test_it_reads_every_block_in_a_file():
    source = 'resource "aws_s3_bucket" "raw" {}\n\nmodule "vpc" {}\nlocals {}\n'
    assert kinds(source) == [
        ('"aws_s3_bucket"', "type"),
        ('"raw"', "name"),
        ('"vpc"', "name"),
    ]


def test_the_columns_are_characters_rather_than_bytes():
    """A text buffer counts characters and the tree counts bytes, and a comment
    with an accent in it is enough to put the two out of step — which puts the
    colour a few characters to the left of the word it is about."""
    source = '# café\nresource "aws_instance" "api" {}\n'
    assert kinds(source) == [('"aws_instance"', "type"), ('"api"', "name")]


def test_an_accent_on_the_same_line_still_lands_on_the_label():
    source = 'resource "aws_instance" "café" {}\n'
    assert kinds(source) == [('"aws_instance"', "type"), ('"café"', "name")]


def test_a_nested_block_is_read_too():
    source = 'resource "aws_instance" "api" {\n  provisioner "local-exec" {}\n}\n'
    assert ('"aws_instance"', "type") in kinds(source)
