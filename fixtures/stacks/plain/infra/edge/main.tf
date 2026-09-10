# Invented.

variable "api_url" {
  type = string
}

resource "terraform_data" "cdn" {
  input = var.api_url
}
