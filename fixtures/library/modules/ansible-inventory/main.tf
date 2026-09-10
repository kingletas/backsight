# ansible inventory — a root nobody calls, which is what makes it a root.

variable "name" {
  type        = string
  description = "What to call it."
}

resource "random_id" "ansible_inventory" {
  byte_length = 4
}
