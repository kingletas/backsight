resource "terraform_data" "first" {
  input = "ok"
}

resource "terraform_data" "second" {
  input = "fails"

  provisioner "local-exec" {
    command = "exit 3"
  }

  depends_on = [terraform_data.first]
}

resource "terraform_data" "third" {
  input      = "never reached"
  depends_on = [terraform_data.second]
}
