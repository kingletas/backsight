# Invented.

variable "private_subnets" {
  type = list(string)
}

variable "database_endpoint" {
  type = string
}

resource "terraform_data" "service" {
  input = var.database_endpoint
}

output "api_url" {
  value = terraform_data.service.output
}
