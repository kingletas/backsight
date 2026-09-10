# Deliberately not formatted. `fmt -check` must refuse this and say what it
# would change; a run where it passes means the check is not running.
resource "aws_s3_bucket"   "ugly" {
    bucket =  "backsight-unformatted"
      force_destroy=true
}
