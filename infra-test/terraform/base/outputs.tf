output "bucket" {
  value       = aws_s3_bucket.objects.id
  description = "The bucket, so a test can go and ask the emulator whether it is there."
}

output "queue_url" {
  value       = aws_sqs_queue.work.url
  description = "The queue's URL, which is what SQS is addressed by."
}

output "table" {
  value       = aws_dynamodb_table.records.name
  description = "The table, by name."
}

output "account" {
  value       = data.aws_caller_identity.current.account_id
  description = "Who the emulator thinks we are. Read to prove `sts` answered."
}

output "delay" {
  value       = aws_sqs_queue.work.delay_seconds
  description = "Echoed back so an update can be seen in the state as well as in the API."
}
