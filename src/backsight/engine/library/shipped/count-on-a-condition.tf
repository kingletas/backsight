# name: count on a condition
# kind: snippet
# tags: meta, count, conditional
# about: One or none, by a boolean. Everything that refers to it needs the
#        `[0]`, which is the part people forget.

resource "${1:terraform_data}" "${2:name}" {
  count = ${3:var.enabled} ? 1 : 0

  input = "${4:value}"
}

# Referred to as: ${1}.${2}[0].id
