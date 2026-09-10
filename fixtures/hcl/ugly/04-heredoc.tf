resource "local_file" "c" {
  content = <<EOF
line one
  indented
EOF
  filename = "c.txt"
}
