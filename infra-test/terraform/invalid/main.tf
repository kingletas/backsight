# Deliberately invalid: `aws_s3_bucket` has no `nonsense` argument, and
# `aws_sqs_queue.absent` is not declared anywhere. **Two different failures on
# purpose** — one the schema catches and one the reference graph does.
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

resource "aws_s3_bucket" "wrong" {
  bucket   = "backsight-invalid"
  nonsense = true
}

output "dangling" {
  value = aws_sqs_queue.absent.url
}
