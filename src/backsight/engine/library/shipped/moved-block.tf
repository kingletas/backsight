# name: moved block
# kind: snippet
# tags: meta, refactor, moved
# about: Renaming a resource without destroying it. Terraform matches on the
#        address, so a rename is a destroy and a create until you say this.

moved {
  from = ${1:terraform_data.old_name}
  to   = ${2:terraform_data.new_name}
}
