"""What a change does to the bill, and — mostly — when that cannot be said.

No prices ship with this application. A price invented from memory is a
confident number about somebody else's money.
"""

from __future__ import annotations

import json

from backsight.engine.plan.model import Action, Plan, ResourceChange
from backsight.engine.policy.cost import Known, Prices, directory, estimate, load


def a_plan(*pairs) -> Plan:
    return Plan(
        format_version="1.2",
        engine_version="1.12.6",
        changes=tuple(
            ResourceChange(f"{type_}.x", type_, "x", "managed", "p", action)
            for type_, action in pairs
        ),
    )


def a_table(**monthly) -> Prices:
    return Prices(monthly=dict(monthly), by_usage=frozenset({"aws_s3_bucket"}))


def test_nothing_ships_with_prices_in_it(tmp_path):
    """Empty is the ordinary state, and the answer says so rather than zero."""
    prices = load(tmp_path)
    assert not prices.any
    found = estimate(a_plan(("aws_instance", Action.CREATE)), prices)
    assert found.headline == "No prices imported yet, so nothing can be estimated"
    assert found.difference == 0.0


def test_an_engine_resource_is_free_because_there_is_nothing_to_bill(tmp_path):
    """Not "priced at zero" — no object exists anywhere for anybody to bill."""
    found = estimate(a_plan(("terraform_data", Action.CREATE)), a_table(aws_instance=10.0))
    assert found.lines[0].known is Known.FREE
    assert "nothing to bill" in found.lines[0].summary


def test_a_usage_priced_resource_is_marked_rather_than_reported_as_zero():
    """A bill that says nothing is one somebody checks; a bill that says zero
    is one they trust."""
    found = estimate(a_plan(("aws_s3_bucket", Action.CREATE)), a_table(aws_instance=10.0))
    assert found.lines[0].known is Known.USAGE
    assert not found.lines[0].is_estimable
    assert found.unestimable


def test_a_type_with_no_price_says_so(tmp_path):
    found = estimate(a_plan(("aws_kinesis_stream", Action.CREATE)), a_table(aws_instance=10.0))
    assert found.lines[0].known is Known.UNKNOWN


def test_creating_something_priced_adds_its_price():
    found = estimate(a_plan(("aws_instance", Action.CREATE)), a_table(aws_instance=12.5))
    assert found.difference == 12.5
    assert found.headline.startswith("+12.50 USD")


def test_destroying_it_takes_it_off():
    found = estimate(a_plan(("aws_instance", Action.DELETE)), a_table(aws_instance=12.5))
    assert found.difference == -12.5


def test_changing_it_in_place_costs_the_same():
    found = estimate(a_plan(("aws_instance", Action.UPDATE)), a_table(aws_instance=12.5))
    assert found.difference == 0.0


def test_a_no_op_is_not_a_line_at_all():
    found = estimate(a_plan(("aws_instance", Action.NO_OP)), a_table(aws_instance=12.5))
    assert found.lines == ()


def test_an_incomplete_estimate_says_so_with_a_tilde():
    """`~14` and `14` say different things."""
    plan = a_plan(("aws_instance", Action.CREATE), ("aws_s3_bucket", Action.CREATE))
    found = estimate(plan, a_table(aws_instance=12.5))
    assert not found.is_complete
    assert found.headline.startswith("~+12.50")
    assert "cannot be estimated" in found.headline


def test_a_complete_estimate_has_no_tilde():
    found = estimate(a_plan(("aws_instance", Action.CREATE)), a_table(aws_instance=12.5))
    assert found.is_complete
    assert "~" not in found.headline


def test_no_plan_is_no_lines_rather_than_a_zero(tmp_path):
    assert estimate(None, load(tmp_path)).lines == ()


def test_an_imported_table_is_read_back(tmp_path):
    where = directory(tmp_path)
    where.mkdir(parents=True)
    (where / "prices.json").write_text(
        json.dumps(
            {"monthly": {"aws_instance": 8.0}, "by_usage": ["aws_s3_bucket"], "currency": "USD"}
        ),
        encoding="utf-8",
    )
    prices = load(tmp_path)
    assert prices.any
    assert prices.monthly_for("aws_instance") == 8.0
    assert prices.known_for("aws_s3_bucket") is Known.USAGE


def test_a_table_that_will_not_read_is_an_empty_one(tmp_path):
    where = directory(tmp_path)
    where.mkdir(parents=True)
    (where / "prices.json").write_text("{ not json", encoding="utf-8")
    assert not load(tmp_path).any
