# Invented. Consumes the network stack's outputs through variables.

variable "vpc_id" {
  type = string
}

variable "private_subnets" {
  type = list(string)
}

resource "terraform_data" "database" {
  input = var.vpc_id
}

output "database_endpoint" {
  value = terraform_data.database.output
}
