# name: A workspace worth copying
# kind: example
# tags: structure, backend, versions
# about: What a root module has before it has anything else — pinned versions,
#        a backend, and the variables that make it an environment rather than
#        a copy. Everything in it is invented.

terraform {
  # Pinned. A range means a colleague can get a different provider than you.
  required_version = "~> 1.12"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.82"
    }
  }

  # State somewhere both of you can reach, with locking, so two applies
  # cannot run at once.
  backend "s3" {
    bucket       = "invented-terraform-state"
    key          = "invented/prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

variable "region" {
  type        = string
  description = "Which region this environment lives in."
  default     = "us-east-1"
}

variable "environment" {
  type        = string
  description = "Which environment this root module is."
}
