# name: Recover from an apply that stopped part way
# kind: runbook
# tags: apply, recovery, state
# about: Some resources changed, one failed, and the rest never started. The
#        state and the code now disagree and neither is wrong.

# step: Read what actually happened before changing anything
The apply screen names each resource: what was created, what failed, and what
was never started. Those are three different situations and only the middle
one needs a decision.

# step: Check whether the failed resource exists anyway
# run: tofu plan -refresh-only
A create that errored may have made the object and marked it tainted. The
refresh tells you what the provider can actually see, which is the only
authority here.

# step: Fix the cause, not the state
The failure had a reason — a quota, a name already taken, a permission. Change
the configuration so the same apply would succeed. Editing state by hand is
the step that turns one bad afternoon into a week.

# step: Plan again and read it as if it were new
# run: tofu plan
It is new. Half of it already happened, so the plan is smaller than the one you
started with, and anything in it you did not expect is worth stopping for.
