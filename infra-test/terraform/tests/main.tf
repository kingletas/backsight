# The happy path: one resource per emulated service, each cheap to create and
# each answerable by an API call afterwards. **Everything in it is invented.**
#
# Nothing here is chosen to raise coverage. It is the three services the
# application's own fixtures already exercise — S3, SQS and DynamoDB — plus the
# caller identity every AWS configuration reads.

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "name" {
  type        = string
  default     = "backsight-integration"
  description = "What every object here is named from, so one run cannot see another's."
}

variable "queue_delay" {
  type        = number
  default     = 0
  description = "Seconds a message waits before it is deliverable. Changed by the update case."
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "objects" {
  bucket        = "${var.name}-objects"
  force_destroy = true
}

resource "aws_sqs_queue" "work" {
  name                       = "${var.name}-work"
  delay_seconds              = var.queue_delay
  visibility_timeout_seconds = 30
}

resource "aws_dynamodb_table" "records" {
  name         = "${var.name}-records"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}
