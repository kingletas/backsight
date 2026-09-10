variable "environment" {
  type        = string
  description = "Which environment this stands up."
}

variable "region" {
  type        = string
  default     = "eu-west-1"
  description = "Where it stands up."
}
