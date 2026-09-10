# Everything in this module is invented.

variable "name" {
  type        = string
  description = "What this queue is called."
}

variable "secret_token" {
  type        = string
  description = "Something the queue needs and nobody should see."
  sensitive   = true
}

resource "terraform_data" "queue" {
  input = var.name
}

output "url" {
  description = "Where to send things."
  value       = terraform_data.queue.output
}
