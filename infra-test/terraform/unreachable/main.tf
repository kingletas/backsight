# A provider that does not exist, so `init` has something real to fail on.
# The registry lookup is what fails, which is the ordinary shape of a broken
# init and the one worth having a case for.
terraform {
  required_providers {
    nowhere = {
      source  = "backsight/definitely-not-a-real-provider"
      version = "= 0.0.1"
    }
  }
}
