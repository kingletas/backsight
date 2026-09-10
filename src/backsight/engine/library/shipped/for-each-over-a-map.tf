# name: for_each over a map
# kind: snippet
# tags: meta, for_each, count
# about: The key becomes part of the address, so adding an entry never moves
#        the others. This is the one that stops a list index shifting and
#        destroying the wrong thing.

resource "${1:terraform_data}" "${2:name}" {
  for_each = ${3:var.things}

  input = each.value
}
