# ssh key pair — a root nobody calls, which is what makes it a root.

variable "name" {
  type        = string
  description = "What to call it."
}

resource "random_id" "ssh_key_pair" {
  byte_length = 4
}
