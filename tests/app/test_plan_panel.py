"""The plan, arranged for reading.

The arrangement is engine-side on purpose, so it can be checked without a
display and so a second front end cannot describe the same plan differently.
"""

from pathlib import Path

from backsight.engine.plan.model import Action, parse, read
from backsight.engine.plan.view import headline, rows, warning

ROOT = Path(__file__).resolve().parents[2]
PLANS = ROOT / "fixtures" / "plan"


def test_a_create_reads_as_an_add():
    row = rows(read(PLANS / "create.json"))[0]
    assert (row.mark, row.label, row.tone) == ("+", "Add", "add")
    assert row.needs_a_second_look is False


def test_an_update_reads_as_a_change_in_place():
    row = rows(read(PLANS / "update.json"))[0]
    assert (row.mark, row.label, row.tone) == ("~", "Change in place", "change")
    assert row.needs_a_second_look is False


def test_a_destroy_is_marked_and_named_and_not_only_coloured():
    """NFR-15. Take the colour away and it still says Destroy, with a mark."""
    row = rows(read(PLANS / "destroy.json"))[0]
    assert row.label == "Destroy"
    assert row.mark == "-"
    assert row.needs_a_second_look is True


def test_a_replace_is_distinct_from_both_an_update_and_a_destroy():
    row = rows(read(PLANS / "replace.json"))[0]
    assert (row.mark, row.label) == ("±", "Replace")
    assert row.mark != "~" and row.mark != "-"
    assert row.needs_a_second_look is True


def test_a_replacement_says_which_attribute_caused_it():
    row = rows(read(PLANS / "replace.json"))[0]
    assert row.reason == "replaced because triggers_replace cannot be changed in place"


def test_a_no_op_is_not_shown_as_a_change():
    plan = read(PLANS / "moved.json")
    assert rows(plan) == []
    assert headline(plan) == "no changes"


def test_the_destructive_rows_come_first():
    """A reviewer's attention is finite, and this is what it is for."""
    document = {
        "format_version": "1.2",
        "terraform_version": "1.12.6",
        "resource_changes": [
            {
                "address": f"null_resource.{name}",
                "type": "null_resource",
                "name": name,
                "mode": "managed",
                "provider_name": "null",
                "change": {"actions": actions},
            }
            for name, actions in (
                ("added", ["create"]),
                ("changed", ["update"]),
                ("destroyed", ["delete"]),
                ("replaced", ["delete", "create"]),
            )
        ],
    }
    ordered = [row.action for row in rows(parse(document))]
    assert ordered == [Action.DELETE, Action.REPLACE, Action.UPDATE, Action.CREATE]


def test_a_plan_that_destroys_nothing_carries_no_warning():
    assert warning(read(PLANS / "create.json")) == ""


def test_a_plan_that_destroys_says_how_many_in_words():
    assert warning(read(PLANS / "destroy.json")) == "1 to be destroyed"
    assert warning(read(PLANS / "replace.json")) == "1 to be destroyed and recreated"


def test_a_plan_that_destroys_and_replaces_does_not_stutter():
    """Both halves say "destroyed", so joining them read as a stutter and made
    the reader count the word rather than the resources."""
    import json
    import tempfile

    destroy = json.loads((PLANS / "destroy.json").read_text(encoding="utf-8"))
    replace = json.loads((PLANS / "replace.json").read_text(encoding="utf-8"))
    both = dict(destroy)
    both["resource_changes"] = destroy["resource_changes"] + replace["resource_changes"]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(both, handle)
        merged = Path(handle.name)
    said = warning(read(merged))
    assert said == "2 destroyed — 1 of them recreated after"
    assert said.count("destroy") == 1


def test_a_module_is_carried_so_a_row_can_say_where_it_lives():
    document = {
        "format_version": "1.2",
        "terraform_version": "1.12.6",
        "resource_changes": [
            {
                "address": "module.network.aws_subnet.a",
                "type": "aws_subnet",
                "name": "a",
                "mode": "managed",
                "provider_name": "aws",
                "change": {"actions": ["create"]},
            }
        ],
    }
    assert rows(parse(document))[0].module == "module.network"
