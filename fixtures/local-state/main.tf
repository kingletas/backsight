# A workspace that plans offline: the engine's own resource, no provider, no
# credentials, no network. Everything in it is invented.

resource "terraform_data" "api" {
  input = "one"
}

resource "terraform_data" "worker" {
  input = "two"
}
