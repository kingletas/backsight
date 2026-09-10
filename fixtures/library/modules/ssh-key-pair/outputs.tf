output "id" {
  value       = random_id.ssh_key_pair.hex
  description = "A handle for it."
}
