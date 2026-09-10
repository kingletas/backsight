module "services" {
  source = "./services"
}

moved {
  from = terraform_data.api
  to   = module.services.terraform_data.api
}

moved {
  from = terraform_data.worker
  to   = module.services.terraform_data.worker
}
