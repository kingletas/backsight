resource "aws_s3_bucket" "a" {
	bucket = "one"
    tags = {
		Name = "a"
    }
}
