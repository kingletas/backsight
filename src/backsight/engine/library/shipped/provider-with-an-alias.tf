# name: provider with an alias
# kind: snippet
# tags: providers, multi-region
# about: A second copy of a provider, for another region or another account.
#        Every resource using it needs the `provider =` line.

provider "${1:aws}" {
  alias  = "${2:secondary}"
  region = "${3:us-west-2}"
}

resource "${4:terraform_data}" "${5:name}" {
  provider = ${1}.${2}
}
