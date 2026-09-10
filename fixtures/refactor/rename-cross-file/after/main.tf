resource "terraform_data" "api_gateway" {
  input = "one"
}

moved {
  from = terraform_data.api
  to   = terraform_data.api_gateway
}
