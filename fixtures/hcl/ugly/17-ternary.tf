locals {
  p = var.env == "prod" ? var.big : var.small
}
