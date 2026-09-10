resource "aws_s3_bucket" "invented" {
  bucket = "invented-bucket-name"
}

resource "aws_security_group" "invented" {
  name = "invented"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
