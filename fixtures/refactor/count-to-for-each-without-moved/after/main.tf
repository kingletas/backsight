resource "terraform_data" "n" {
  for_each = {
    a = "value-0"
    b = "value-1"
    c = "value-2"
  }
  input    = each.value
}
