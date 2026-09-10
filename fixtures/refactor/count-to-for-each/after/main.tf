resource "terraform_data" "n" {
  for_each = {
    a = "value-0"
    b = "value-1"
    c = "value-2"
  }
  input    = each.value
}

moved {
  from = terraform_data.n[0]
  to   = terraform_data.n["a"]
}

moved {
  from = terraform_data.n[1]
  to   = terraform_data.n["b"]
}

moved {
  from = terraform_data.n[2]
  to   = terraform_data.n["c"]
}
