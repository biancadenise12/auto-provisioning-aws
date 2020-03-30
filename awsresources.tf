locals {
    json_input = jsondecode(file("input.json"))
}

resource "aws_instance" "server" {
  instance_type = local.json_input.details.size
  ami = local.json_input.details.image
  count = local.json_input.details.number_of_resource
}