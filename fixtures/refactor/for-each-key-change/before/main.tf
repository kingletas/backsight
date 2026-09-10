resource "terraform_data" "n" {
  for_each = { old = "one" }
  input = each.value
}
