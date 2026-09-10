"""Reading a module well enough to call it correctly.

The fixtures are two invented modules built on the engine's own resource, so
they need no provider and every value in them is made up.
"""

from __future__ import annotations

from pathlib import Path

from backsight.engine.catalog.modules import catalog, read
from backsight.engine.hcl.navigation import blocks
from backsight.engine.library.placeholders import resolve

FIXTURES = Path(__file__).resolve().parents[1].parent / "fixtures" / "catalog"


def network():
    return read(FIXTURES / "network")


def test_a_module_is_read_by_its_variables_and_outputs():
    found = network()
    assert [one.name for one in found.inputs] == ["name", "cidr", "tags", "subnet_count"]
    assert [one.name for one in found.outputs] == ["id", "subnets"]


def test_each_input_carries_its_type_and_what_it_is_for():
    one = next(i for i in network().inputs if i.name == "cidr")
    assert one.type == "string"
    assert one.description == "The address range this network covers."


def test_no_default_means_the_module_will_not_plan_without_it():
    found = network()
    assert [one.name for one in found.required] == ["name", "cidr"]
    assert not next(i for i in found.inputs if i.name == "tags").is_required


def test_a_sensitive_input_is_known_to_be_one():
    queue = read(FIXTURES / "queue")
    assert next(i for i in queue.inputs if i.name == "secret_token").sensitive


def test_the_readme_says_what_the_module_is():
    assert network().about.startswith("A network with subnets")


def test_a_module_with_no_readme_still_reads():
    assert read(FIXTURES / "queue").about == ""


def test_the_summary_counts_what_matters_to_a_caller():
    assert network().summary == "2 required inputs · 2 outputs"


# --- calling one -----------------------------------------------------------


def test_it_writes_a_call_with_every_required_input():
    said = network().call()
    assert 'module "${1:network}"' in said
    assert "source = " in said
    assert "name" in said and "cidr" in said


def test_an_optional_input_is_left_out():
    """A call carrying every optional argument at its default is a call nobody
    can read."""
    said = network().call()
    assert "tags" not in said
    assert "subnet_count" not in said


def test_the_call_is_terraform_that_parses():
    text = resolve(network().call()).text
    assert blocks(text.encode("utf-8"))


def test_a_placeholder_is_shaped_like_the_type_the_module_asked_for():
    from backsight.engine.catalog.modules import Input, Module

    module = Module(
        name="x",
        path=Path("x"),
        inputs=(
            Input(name="count_of", type="number"),
            Input(name="enabled", type="bool"),
            Input(name="names", type="list(string)"),
            Input(name="tags", type="map(string)"),
        ),
    )
    said = module.call()
    assert "= ${2:0}" in said
    assert "= ${3:false}" in said
    assert "= [${4}]" in said
    assert "= {" in said


def test_the_source_can_be_given_rather_than_guessed():
    said = network().call(source="git::https://example.invalid/modules//network", name="core")
    assert "git::https://example.invalid/modules//network" in said
    assert '"${1:core}"' in said


# --- a directory of them ---------------------------------------------------


def test_a_catalog_is_every_module_directory_in_it():
    found = catalog(FIXTURES)
    assert [one.name for one in found] == ["network", "queue"]


def test_a_directory_with_no_terraform_in_it_is_not_a_module(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "readme.txt").write_text("nothing", encoding="utf-8")
    assert catalog(tmp_path) == []


def test_a_catalog_that_is_not_there_is_not_a_failure(tmp_path):
    assert catalog(tmp_path / "nowhere") == []


def test_searching_reaches_the_name_the_prose_and_the_inputs():
    found = catalog(FIXTURES)
    assert [one.name for one in found if one.matches("subnets")] == ["network"]
    assert [one.name for one in found if one.matches("queue")] == ["queue"]
    assert [one.name for one in found if one.matches("secret_token")] == ["queue"]


# --- in the library --------------------------------------------------------


def test_a_module_becomes_a_library_entry():
    """Where an approved module exists for the thing somebody is writing, it
    belongs in front of them at the same moment as the raw resource type."""
    from backsight.engine.catalog.modules import as_entries

    entries = as_entries(catalog(FIXTURES))
    assert [one.name for one in entries] == ["network (module)", "queue (module)"]
    assert all("module" in one.tags for one in entries)


def test_the_entry_body_is_a_call_that_parses():
    from backsight.engine.catalog.modules import as_entries

    for one in as_entries(catalog(FIXTURES)):
        assert blocks(resolve(one.body).text.encode("utf-8")), one.name


def test_a_shared_source_reaches_the_generated_call():
    from backsight.engine.catalog.modules import as_entries

    entries = as_entries(catalog(FIXTURES), source="git::https://example.invalid/modules")
    assert "git::https://example.invalid/modules//network" in entries[0].body


def test_a_module_that_will_not_read_is_left_out_rather_than_offered(tmp_path):
    from backsight.engine.catalog.modules import Module, as_entries

    broken = Module(name="broken", path=tmp_path, unreadable="it will not parse")
    assert as_entries([broken]) == []
