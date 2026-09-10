"""Why is this being replaced — the question the plan does not answer."""

from backsight.engine.insight.trace import replacement_trace
from backsight.engine.plan.model import parse

DOCUMENT = {
    "format_version": "1.2",
    "terraform_version": "1.12.6",
    "resource_changes": [
        {
            "address": "aws_instance.api",
            "type": "aws_instance",
            "name": "api",
            "mode": "managed",
            "provider_name": "aws",
            "action_reason": "replace_because_cannot_update",
            "change": {
                "actions": ["delete", "create"],
                "before": {"instance_type": "m6i.xlarge"},
                "after": {"instance_type": "m6i.2xlarge"},
                "replace_paths": [["instance_type"]],
            },
        },
        {
            "address": "aws_lb_target_group_attachment.api",
            "type": "aws_lb_target_group_attachment",
            "name": "api",
            "mode": "managed",
            "provider_name": "aws",
            "change": {"actions": ["update"], "before": {}, "after": {}},
        },
    ],
    "configuration": {
        "root_module": {
            "resources": [
                {
                    "address": "aws_instance.api",
                    "expressions": {"instance_type": {"references": ["var.api_instance_type"]}},
                },
                {
                    "address": "aws_lb_target_group_attachment.api",
                    "expressions": {
                        "target_id": {"references": ["aws_instance.api.id", "aws_instance.api"]}
                    },
                },
            ]
        }
    },
}

PLAN = parse(DOCUMENT)


def test_a_resource_that_is_not_being_replaced_has_no_trace():
    assert replacement_trace(PLAN, DOCUMENT, "aws_lb_target_group_attachment.api") is None


def test_a_resource_that_is_not_in_the_plan_has_no_trace():
    assert replacement_trace(PLAN, DOCUMENT, "aws_instance.nowhere") is None


def test_the_trace_names_the_attribute_that_forced_it():
    trace = replacement_trace(PLAN, DOCUMENT, "aws_instance.api")
    assert trace.is_explained
    assert trace.attributes == ("instance_type",)
    assert "forced by instance_type — cannot be changed in place" in trace.lines()


def test_the_trace_shows_both_values():
    """Naming both sides is what makes it actionable rather than informational."""
    trace = replacement_trace(PLAN, DOCUMENT, "aws_instance.api")
    assert 'changed — "m6i.xlarge" → "m6i.2xlarge"' in trace.lines()


def test_the_trace_ends_at_the_variable_and_not_at_the_attribute():
    """Every other tool stops one step earlier."""
    trace = replacement_trace(PLAN, DOCUMENT, "aws_instance.api")
    assert "value from var.api_instance_type" in trace.lines()


def test_the_downstream_consequences_are_named():
    """A new id ripples, and the plan shows those as updates without saying why."""
    trace = replacement_trace(PLAN, DOCUMENT, "aws_instance.api")
    assert trace.downstream == ("aws_lb_target_group_attachment.api",)
    assert trace.consequence() == "1 resource depend on this and will see a new id."


def test_nothing_downstream_says_so_plainly():
    document = {**DOCUMENT, "configuration": {"root_module": {"resources": []}}}
    trace = replacement_trace(parse(document), document, "aws_instance.api")
    assert trace.consequence() == "Nothing else in this plan depends on it."


def test_a_replacement_with_no_named_attribute_says_so_rather_than_guessing():
    document = {
        "format_version": "1.2",
        "terraform_version": "1.12.6",
        "resource_changes": [
            {
                "address": "aws_instance.api",
                "type": "aws_instance",
                "name": "api",
                "mode": "managed",
                "provider_name": "aws",
                "action_reason": "replace_because_tainted",
                "change": {"actions": ["delete", "create"]},
            }
        ],
    }
    trace = replacement_trace(parse(document), document, "aws_instance.api")
    assert trace.is_explained is False
    assert "the plan does not name an attribute — replace_because_tainted" in trace.lines()


def test_a_sensitive_value_is_not_shown_in_the_trace():
    """FR-DBG-06 has no exceptions, and a trace is a place it would be forgotten."""
    document = {
        "format_version": "1.2",
        "terraform_version": "1.12.6",
        "resource_changes": [
            {
                "address": "aws_db_instance.main",
                "type": "aws_db_instance",
                "name": "main",
                "mode": "managed",
                "provider_name": "aws",
                "change": {
                    "actions": ["delete", "create"],
                    "before": {"password": "old-secret"},
                    "after": {"password": "new-secret"},
                    "after_sensitive": {"password": True},
                    "replace_paths": [["password"]],
                },
            }
        ],
    }
    trace = replacement_trace(parse(document), document, "aws_db_instance.main")
    said = " ".join(trace.lines())
    assert "old-secret" not in said
    assert "new-secret" not in said
    assert "(sensitive — not shown)" in said
