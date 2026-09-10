output "id" {
  value       = random_id.ansible_inventory.hex
  description = "A handle for it."
}
