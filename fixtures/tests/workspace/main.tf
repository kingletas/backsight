variable "count_of" {
  type    = number
  default = 3
}

resource "terraform_data" "nodes" {
  count = var.count_of
  input = "node-${count.index}"
}

output "names" {
  value = [for n in terraform_data.nodes : n.input]
}
