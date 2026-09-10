# Invented. No provider, no credentials, no network.

resource "terraform_data" "vpc" {
  input = "invented-vpc"
}

output "vpc_id" {
  value = terraform_data.vpc.output
}

output "private_subnets" {
  value = ["invented-a", "invented-b"]
}

output "public_subnets" {
  value = ["invented-c"]
}
