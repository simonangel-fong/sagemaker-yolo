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
variable "model_run" {
  description = "Model basename under deploy/ in S3. Packaged by deploy/package.py."
  type        = string
  default     = "tune-cpu-556img-640px-epochs30"
}

variable "inference_image_uri" {
  description = "PyTorch inference DLC. Must match aws_region."
  type        = string
  default     = "763104351884.dkr.ecr.ca-central-1.amazonaws.com/pytorch-inference:2.6-cpu-py312"
}

variable "conf_threshold" {
  description = "Minimum detection confidence."
  type        = string
  default     = "0.25"
}

variable "iou_threshold" {
  description = "IoU threshold for NMS."
  type        = string
  default     = "0.45"
}

variable "serverless_memory_mb" {
  description = "Serverless endpoint memory. Must be a multiple of 1024, 1024-6144."
  type        = number
  default     = 3072

  validation {
    condition     = contains([1024, 2048, 3072, 4096, 5120, 6144], var.serverless_memory_mb)
    error_message = "serverless_memory_mb must be one of 1024, 2048, 3072, 4096, 5120, 6144."
  }
}

variable "serverless_max_concurrency" {
  description = "Concurrent invocations before throttling."
  type        = number
  default     = 5

  validation {
    condition     = var.serverless_max_concurrency >= 1 && var.serverless_max_concurrency <= 200
    error_message = "serverless_max_concurrency must be between 1 and 200."
  }
}

# ##############################
# Web app
# ##############################
variable "web_model_name" {
  description = "Model name the browser client uses in its request path."
  type        = string
  default     = "yolo-car-plate"
}

variable "allow_origin" {
  description = "CORS origin allowed to call the predict function."
  type        = string
  default     = "*"
}

# ##############################
# Custom domain
# ##############################
variable "web_domain" {
  description = "Custom domain the web app is served on."
  type        = string
  default     = "yolo.arguswatcher.net"
}

# Looked up in us-east-1, not created. Must already cover web_domain.
variable "acm_certificate_domain" {
  description = "Domain of the existing ACM certificate to serve the app with."
  type        = string
  default     = "*.arguswatcher.net"
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
