terraform {
  required_version = ">= 1.9"

  backend "s3" {
    bucket = "example-state"
    key    = "prod/terraform.tfstate"
    region = "eu-west-1"
  }

  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.82" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}

module "vpc" {
  source = "../../modules/vpc"
  name   = "prod"
}
