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

  # ##############################
  # Experiments
  # ##############################
  # fast launch ml.t3.xlarge;GP CPU ml.c5.large; GPU-powered ml.g4dn.xlarge
  sagemaker_notebook_instance_type = "ml.g4dn.xlarge"
  sagemaker_notebook_volume_size   = 10
}
