# variables-deploy.tf

# ##############################
# Control
# ##############################
variable "enable_deploy" {
  description = "Whether to enable deployment."
  type        = bool
  default     = true
}

# ##############################
# Endpoint
# ##############################
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
# DNS
# ##############################
# domain name


variable "cloudflare_api_token" {
  description = "Cloudflare token with DNS edit rights on the zone."
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone id for the domain's root zone."
  type        = string
}
