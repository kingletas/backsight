# Values with no infrastructure behind them, so reading state back can be
# tested without waiting for anything to be created. `terraform_data` is the
# engine's own resource: no provider, no credentials, no network.

variable "environment" {
  type        = string
  default     = "integration"
  description = "Echoed into every output, so a variable can be seen to arrive."
}

resource "terraform_data" "marker" {
  input = "marked-${var.environment}"
}

output "marker" {
  value       = terraform_data.marker.output
  description = "What the resource was given, read back from state."
}

output "environment" {
  value       = var.environment
  description = "The variable itself, to prove one was passed in."
}

output "a_number" {
  value       = 42
  description = "A non-string, because JSON types are where a reader gets it wrong."
}

output "a_list" {
  value       = ["one", "two"]
  description = "And a collection, for the same reason."
}
