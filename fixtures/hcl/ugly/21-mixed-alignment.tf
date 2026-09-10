resource "aws_db_instance" "s" {
  identifier="orders"
  engine        = "postgres"
    storage_encrypted =true
}
