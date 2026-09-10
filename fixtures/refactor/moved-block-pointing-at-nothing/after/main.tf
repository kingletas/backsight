resource "terraform_data" "api_gateway" {
  input = "one"
}

moved {
  from = terraform_data.wrong_name
  to   = terraform_data.api_gateway
}
