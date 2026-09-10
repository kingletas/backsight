# name: Move a resource without destroying it
# kind: runbook
# tags: refactor, moved, safe
# about: Renaming, or moving into a module. Terraform matches on the address,
#        so without this it is a destroy and a create.

# step: Write the moved block before you rename anything
Put it in the same file. `from` is the address as it is now, `to` is what you
are about to call it.

moved {
  from = terraform_data.old_name
  to   = terraform_data.new_name
}

# step: Rename the resource itself, and every reference to it
Find all references first — a reference you miss is an error at plan time
rather than a silent one, but finding them is faster than reading them.

# step: Plan, and read the count before anything else
# run: tofu plan
A correct move plans zero to add and zero to destroy. Anything else means the
address in the moved block does not match, and applying it would destroy the
resource you were trying to keep.

# step: Apply, then delete the moved block on a later change
It has done its work once the state has moved. Leaving it is harmless and
leaving it forever is clutter.
