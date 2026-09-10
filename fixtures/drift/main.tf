terraform {
  required_providers {
    local = {
      source  = "opentofu/local"
      version = "~> 2.5"
    }
  }
}

resource "local_file" "config" {
  filename = "${path.module}/generated/app.conf"
  content  = "mode = production\n"
}

resource "local_file" "notes" {
  filename = "${path.module}/generated/notes.txt"
  content  = "left alone\n"
}
