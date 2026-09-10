# name: A module worth copying
# kind: example
# tags: module, structure
# about: The shape of a module somebody else can use — every input described,
#        every output named, and nothing hardcoded that a caller might want to
#        change. Everything in it is invented.

variable "name" {
  type        = string
  description = "What this instance of the module is called. Used in every resource name."
}

variable "environment" {
  type        = string
  description = "Which environment this belongs to."

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "The environment must be dev, staging or prod."
  }
}

variable "tags" {
  type        = map(string)
  description = "Anything the caller wants on every resource here."
  default     = {}
}

locals {
  # One place the name is built, so every resource agrees on it.
  full_name = "${var.name}-${var.environment}"

  tags = merge(var.tags, {
    Name        = local.full_name
    Environment = var.environment
    ManagedBy   = "terraform"
  })
}

resource "terraform_data" "this" {
  input = local.full_name
}

output "id" {
  description = "The id of the thing this module made."
  value       = terraform_data.this.id
}

output "name" {
  description = "The full name, so a caller does not rebuild it."
  value       = local.full_name
}
