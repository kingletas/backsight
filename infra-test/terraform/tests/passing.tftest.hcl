# What `terraform test` runs. Against mocks by default — the application's own
# default target — so this needs no emulator and no credentials.

run "the_names_come_from_the_variable" {
  command = plan

  variables {
    name = "backsight-under-test"
  }

  assert {
    condition     = aws_s3_bucket.objects.bucket == "backsight-under-test-objects"
    error_message = "The bucket is not named from the variable."
  }

  assert {
    condition     = aws_sqs_queue.work.name == "backsight-under-test-work"
    error_message = "The queue is not named from the variable."
  }
}

run "the_table_is_billed_per_request" {
  command = plan

  assert {
    condition     = aws_dynamodb_table.records.billing_mode == "PAY_PER_REQUEST"
    error_message = "A provisioned table costs money whether or not anybody uses it."
  }
}
