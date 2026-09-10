# The example workspace. It plans offline against the engine's own resource —
# no provider, no credentials, no network — and every value in it is invented.
#
# The state beside this file says three resources already exist. This file asks
# for something different, so a plan here shows all four kinds of change at
# once rather than an empty diff.

# Changed in place. Reversible, and nothing goes away.
resource "terraform_data" "api" {
  input = "v2"
}

# Replaced. The engine destroys this one and creates a new one, because the
# trigger changed — the same shape as a database engine upgrade.
resource "terraform_data" "database" {
  input            = "primary"
  triggers_replace = "postgres-16"
}

# Added. Nothing exists for it yet.
resource "terraform_data" "worker" {
  input = "queue-consumer"
}

# `old_cache` is in the state and is deliberately absent here, so the plan
# includes a destroy.
