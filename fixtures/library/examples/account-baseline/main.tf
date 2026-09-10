# The account baseline example. Everything in it is invented.

data "aws_caller_identity" "current" {}

locals {
  prefix = format("%s-account-baseline", var.environment)
}

module "context" {
  source = "../../modules/context"

  project     = "account-baseline"
  environment = var.environment
}

module "raw" {
  source = "../../modules/s3-bucket"

  project     = local.prefix
  environment = var.environment
}

module "pipeline_role" {
  source = "../../modules/iam-role"

  project     = local.prefix
  environment = var.environment
}

resource "aws_s3_bucket" "raw" {
  bucket = format("%s-raw", local.prefix)
}

resource "random_pet" "suffix" {
  length = 2
}
