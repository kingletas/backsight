# vpc peering — a root nobody calls, which is what makes it a root.

variable "name" {
  type        = string
  description = "What to call it."
}

resource "random_id" "vpc_peering" {
  byte_length = 4
}
