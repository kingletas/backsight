output "bucket" {
  value       = aws_s3_bucket.raw.id
  description = "Where the raw objects land."
}

output "prefix" {
  value       = module.context.prefix
  description = "What everything else here is named from."
}
