resource "terraform_data" "n" {
  for_each = { new = "one" }
  input = each.value
}

moved {
  from = terraform_data.n["old"]
  to   = terraform_data.n["new"]
}
