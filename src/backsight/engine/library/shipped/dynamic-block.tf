# name: dynamic block
# kind: snippet
# tags: meta, dynamic
# about: Repeating a nested block from a collection. `for_each` here is the
#        collection and `${1}` is what each one is called inside it.

dynamic "${1:setting}" {
  for_each = ${2:var.settings}

  content {
    name  = ${1}.value.name
    value = ${1}.value.value
  }
}
