resource "terraform_data" "n" {
  count = 3
  input = "value-${count.index}"
}
