# name: lifecycle rules
# kind: snippet
# tags: meta, lifecycle
# about: The four that matter. `prevent_destroy` refuses the plan rather than
#        warning, which is what you want on anything holding data.

lifecycle {
  create_before_destroy = ${1:true}
  prevent_destroy       = ${2:false}
  ignore_changes        = [${3:tags}]

  precondition {
    condition     = ${4:var.size > 0}
    error_message = "${5:Say what is wrong and what to set instead.}"
  }
}
