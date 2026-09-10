# Everything in this module is invented.

variable "name" {
  type        = string
  description = "What this network is called."
}

variable "cidr" {
  type        = string
  description = "The address range this network covers."
}

variable "tags" {
  type        = map(string)
  description = "Anything to put on every resource here."
  default     = {}
}

variable "subnet_count" {
  type        = number
  description = "How many subnets to carve out."
  default     = 2
}

resource "terraform_data" "network" {
  input = var.name
}

output "id" {
  description = "The id of the network."
  value       = terraform_data.network.id
}

output "subnets" {
  description = "Every subnet in it."
  value       = [terraform_data.network.output]
}
