# route53 zone — a root nobody calls, which is what makes it a root.

variable "name" {
  type        = string
  description = "What to call it."
}

resource "random_id" "route53_zone" {
  byte_length = 4
}
