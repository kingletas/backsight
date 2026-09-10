run "creates_the_right_number" {
  command = apply

  assert {
    condition     = length(terraform_data.nodes) == 3
    error_message = "expected three nodes"
  }
}

run "names_are_wrong_on_purpose" {
  command = apply

  assert {
    condition     = length(terraform_data.nodes) == 5
    error_message = "expected five nodes"
  }
}
