locals {
  n = "${var.a}-${lower("${var.b}${var.c}")}"
}
