# variables-deploy.tf

# ##############################
# Control
# ##############################
variable "enable_deploy" {
  description = "Whether to enable deployment."
  type        = bool
  default     = false
}

# ##############################
# Endpoint
# ##############################
variable "model_package_group" {
  description = "Model package group the training pipeline registers into."
  type        = string
  default     = "sagemaker-yolo"
}

# the version must be Approved before it can be deployed
variable "model_version" {
  description = "Model package version to deploy."
  type        = number
  default     = 2
}

# ##############################
# lambda function
# ##############################
# lambda image tag
variable "lambda_image_tag" {
  description = "ECR tag of the predict container image to deploy."
  type        = string
  default     = "latest"
}

# ##############################
# Web app
# ##############################
# Custom domain
variable "web_domain" {
  description = "Custom domain the web app is served on."
  type        = string
  default     = "yolo.arguswatcher.net"
}

variable "cloudflare_api_token" {
  description = "Cloudflare token with DNS edit rights on the zone."
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone id for the domain's root zone."
  type        = string
}
