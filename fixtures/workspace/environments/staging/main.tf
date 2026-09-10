terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.82" }
  }
}

module "vpc" {
  source = "../../modules/vpc"
  name   = "staging"
}
