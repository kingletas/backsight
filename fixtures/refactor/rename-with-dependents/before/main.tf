resource "terraform_data" "api" {
  input = "one"
}

resource "terraform_data" "worker" {
  input = terraform_data.api.output
}
