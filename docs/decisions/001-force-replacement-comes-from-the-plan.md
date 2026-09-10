# 001 — Force-replacement comes from the plan, not the schema

**Decided 2026-09-07.** Ruled by the sponsor after finding 001.

## What was chosen

Backsight tells the author that an attribute forces replacement **from the speculative plan**, and says in the interface that that is where the answer comes from.

## What else was considered

Reading it from the mirrored provider documentation, which carries the phrase "Forces new resource" in prose. Rejected as the primary source because the coverage is written by hand and is missing entirely for resources that certainly have force-new arguments — a silent false negative, which is the failure R-3 calls worse than noise. It stays available as an enrichment once the documentation mirror exists, and anything it adds has to be marked as partial.

Building the table another way — reading each provider's Go source, or planning attribute mutations against a fixture workspace — was rejected on ongoing cost per provider and per version.

## Why

The schema cannot answer the question. `tofu providers schema -json` has eight attribute keys and none of them is force-replacement; see finding 001 for the evidence. No implementation choice changes that.

## What it costs

The specific claim in FR-SCH-06 that the fact arrives at the keystroke rather than at plan time. It arrives when the speculative plan lands, which for the target workspace size is seconds rather than the twenty minutes the BRD was written against.

## The same problem, one attribute over

**The schema carries no `default` either.** FR-SCH-05 asks hover to show a default, and the eight keys do not include one; the value lives in the same documentation prose, written by hand, with the same gaps. It is handled the same way by extension of this ruling: hover says nothing about a default rather than guessing one, and the documentation mirror may fill it in later, marked as partial.

**Neither absence may be papered over with a plausible value.** An attribute whose default is unknown says nothing. Inventing `false` because most booleans default to false is how a workbench teaches somebody something untrue.
