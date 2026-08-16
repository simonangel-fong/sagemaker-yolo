# locals.tf

locals {
  # ##############################
  # Metadata
  # ##############################
  project_name = "sagemaker-yolo"
  prefix_name  = "${local.project_name}-${var.env}"
  default_tags = {
    Project   = local.project_name
    Env       = var.env
    ManagedBy = "Terraform"
  }
  github_owner    = "simonangel-fong"
  github_repo     = "sagemaker-yolo"
  github_repo_url = "https://github.com/${local.github_owner}/${local.github_repo}.git"

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
  web_model_name   = local.prefix_name
  web_allow_origin = "*"

  # acm
  acm_certificate_domain = "*.arguswatcher.net"

  # dns
  dns_prefix = "yolo"
  dns_domain = "arguswatcher.net"
  dns_web    = "${local.dns_prefix}.${local.dns_domain}"
}
