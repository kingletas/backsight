# name: variable with validation
# kind: snippet
# tags: variables, validation
# about: A variable that refuses a wrong value at plan time rather than
#        failing at apply. The message is read by whoever got it wrong.

variable "${1:name}" {
  type        = ${2:string}
  description = "${3:What this is for.}"
  default     = ${4:null}

  validation {
    condition     = ${5:can(regex("^[a-z-]+$", var.name))}
    error_message = "${6:Say what is allowed, rather than only what is not.}"
  }
}
