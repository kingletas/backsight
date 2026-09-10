# iam role — called by the examples, so it is a library module.

variable "project" {
  type        = string
  description = "What is being built."
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Where it is being built."
}

output "prefix" {
  value       = format("%s-%s", var.project, var.environment)
  description = "What everything else is named from."
}
