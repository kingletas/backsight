resource "null_resource" "b" {
  triggers = {
    now = "1"
  }
}
