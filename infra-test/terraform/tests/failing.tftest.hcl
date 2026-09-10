# **Deliberately failing**, and it is the more important of the two: a test
# runner that has only ever been seen passing has not been tested. The
# integration suite filters to one file at a time, so this is never run
# alongside the passing one by accident.

run "an_assertion_that_does_not_hold" {
  command = plan

  assert {
    condition     = aws_s3_bucket.objects.bucket == "this-is-not-what-it-is-called"
    error_message = "Deliberate: this is the failure the runner has to report."
  }
}
