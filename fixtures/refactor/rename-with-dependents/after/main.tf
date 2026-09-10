resource "terraform_data" "api_gateway" {
  input = "one"
}

resource "terraform_data" "worker" {
  input = terraform_data.api_gateway.output
}

moved {
  from = terraform_data.api
  to   = terraform_data.api_gateway
}
