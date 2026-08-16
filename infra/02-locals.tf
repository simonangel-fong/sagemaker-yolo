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

  # ##############################
  # Deployment
  # ##############################
  # endpoint
  endpoint_conf_threshold  = "0.25"
  endpoint_memory_mb       = "3072" # must be one of 1024, 2048, 3072, 4096, 5120, 6144
  endpoint_max_concurrency = 5
  # web
  web_model_name   = "yolo-car-plate"
  web_allow_origin = "*"
  # acm
  acm_certificate_domain = "*.arguswatcher.net"
}
