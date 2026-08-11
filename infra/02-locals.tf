# locals.tf

locals {
  # ##############################
  # Metadata
  # ##############################
  prefix_name = "${var.project}-${var.env}"
  default_tags = {
    Project   = var.project
    Env       = var.env
    ManagedBy = "Terraform"
  }
}
