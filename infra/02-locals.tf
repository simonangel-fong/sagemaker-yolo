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
  repo_owner = "simonangel-fong"
  repo_name  = "sagemaker-yolo"
  repo_url   = "https://github.com/${local.repo_owner}/${local.repo_name}.git"

  oidc_sub_prefix    = "repo:${local.repo_owner}@${var.repo_owner_id}/${local.repo_name}@${var.repo_id}"
  oidc_deploy_branch = "master"
  oidc_environment   = "dev"

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

  # Monitoring
  monitoring_log_retention_days = 14
  alarm_endpoint_latency_ms     = 10000
  alarm_lambda_duration_ms      = 25000
  alarm_lambda_invocations_5min = 500

  # finops
  fin_monthly_budget_usd = 10

  # acm
  acm_certificate_domain = "*.arguswatcher.net"

  # dns
  dns_prefix = "yolo"
  dns_domain = "arguswatcher.net"
  dns_web    = "${local.dns_prefix}.${local.dns_domain}"
}
