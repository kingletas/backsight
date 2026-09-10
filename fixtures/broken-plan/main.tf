# A workspace whose plan fails, for showing what the engine said. Invented:
# the variable it references is deliberately never declared.

resource "terraform_data" "api" {
  input = var.missing
}
