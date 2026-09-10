# Resources the emulator implements. Everything here is invented.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.82"
    }
  }
}

resource "aws_s3_bucket" "documents" {
  bucket = "backsight-example-documents"
}

resource "aws_sqs_queue" "work" {
  name = "backsight-example-work"
}

resource "aws_dynamodb_table" "sessions" {
  name         = "backsight-example-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# Deliberately beyond what the light edition implements, so a partial result has
# something real to be partial about.
resource "aws_quicksight_group" "analysts" {
  group_name = "analysts"
}
