# Finding 001 — force-replacement is not in the provider schema

**Status: ruled on 2026-09-07 — the plan is the source. See `docs/decisions/001-force-replacement-comes-from-the-plan.md`.** The evidence below stands as the reason. The requirement rested on a premise that is not true, so it was raised for a ruling rather than quietly dropped or rewritten.

## The claim

BRD FR-SCH-06, one of the five differentiators:

> **Force-replacement is surfaced at authoring time.** The schema declares which attributes are `ForceNew`. The author sees it as they type, not in a plan twenty minutes later.

Design plate 01 draws it against `aws_instance.instance_type`. The schema index took it as its acceptance test, with the note that if the parse is wrong the headline feature is wrong.

## What the schema actually contains

`tofu providers schema -json` for `hashicorp/aws 5.82.2`, 13 MB, 1,470 resources. Across the entire file the set of attribute keys is exactly:

```
computed, deprecated, description, description_kind, optional, required, sensitive, type
```

There is no force-replacement field. The only match for `force_new` anywhere in 13 MB is `force_new_deployment`, an ECS *attribute name*. No description contains the phrase "forces new resource" — the JSON carries none of the registry's prose.

**The schema cannot answer this question.** Not for AWS, not for any provider: the field does not exist in the format.

## Where the fact does live

**In a plan, after the fact.** A forced replacement carries both a reason and the attribute path that caused it:

```json
"actions": ["delete", "create"],
"action_reason": "replace_because_cannot_update",
"replace_paths": [["triggers_replace"]]
```

That is `fixtures/plan/replace.json`, and it is exactly the "in a plan twenty minutes later" that FR-SCH-06 exists to beat.

**In the provider's prose documentation, partially.** The AWS provider's markdown writes `* \`vpc_id\` - (Optional, Forces new resource)`. But the coverage is inconsistent, because a human types it:

| Resource | Attributes marked "Forces new resource" |
|---|---|
| `aws_security_group` | 4 |
| `aws_s3_bucket` | 3 |
| `aws_db_instance` | 3 |
| `aws_subnet` | **0** |
| `aws_ecs_cluster` | **0** |
| `aws_lambda_function` | **0** |

`aws_subnet` certainly has force-new arguments. The doc does not say so. A parser over this source is right where the prose is right and silently wrong everywhere else — which is the false-negative failure R-3 calls worse than noise, moved from the exposure analyser into the editor.

## And the example itself is wrong

`aws_instance.instance_type` **does not force replacement.** The provider's own documentation says:

> Updates to this field will trigger a stop/start of the EC2 instance.

It is an in-place update. So plate 01's annotation, and the schema index's acceptance test, both assert something untrue about the resource they chose to demonstrate it on. It probably was ForceNew years ago; it is not now.

## What this leaves

Three options, and the choice is a product decision rather than an implementation one.

1. **Serve it from the docs mirror and mark the gaps.** Honest, partial, and requires saying "unknown" rather than "no" for every attribute the prose does not mention. Needs the documentation mirror, which the agreed MVP cut currently excludes.
2. **Serve it from the speculative plan.** Accurate and complete, and it is a plan result rather than a keystroke result — which is a real feature, just not this one.
3. **Build the table another way** — read it out of each provider's Go source, or derive it by planning attribute mutations against a fixture workspace. Accurate, and a large ongoing cost per provider and per version.

There is no fourth option where the schema answers it.

## Recommended

**Option 2 for the MVP, and say so plainly in the interface.** It is truthful, it needs no new source, and the speculative plan is already in the cut. Then option 1 as an enrichment once the docs mirror exists, marked as partial wherever the prose is silent.

What this costs is the specific claim that the fact arrives at the keystroke. That claim cannot be met from the schema by anyone, including the tools the BRD compares against.

**Unblocked by the ruling.** The schema index records what the schema carries and asserts nothing about replacement; the hover reads the plan.
