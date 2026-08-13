# variables.tf

# ##############################
# Metadata
# ##############################
variable "project" {
  description = "Project name"
  default     = "sagemaker-yolo"
}

variable "env" {
  description = "Environmet"
  default     = "dev"
}

variable "git_repository_url" {
  description = "HTTPS URL offered in the JupyterLab clone menu."
  type        = string
}

# ##############################
# Providers: aws
# ##############################
variable "aws_region" {
}

# ##############################
# Control
# ##############################
variable "enable_experiment" {
  description = "Whether to enable studio notebook space and MLflow tracking server."
  type        = bool
  default     = true
}

variable "enable_deploy" {
  description = "Whether to enable deployment."
  type        = bool
  default     = false
}

# ##############################
# VPC
# ##############################
variable "vpc_id" {
  description = "Existing VPC to place the Studio domain in."
  type        = string

  validation {
    condition     = can(regex("^vpc-[0-9a-f]{8,17}$", var.vpc_id))
    error_message = "vpc_id must look like vpc-xxxxxxxx."
  }
}

# Studio apps pull pip packages, so these need an IGW or NAT route.
variable "public_subnet_ids" {
  description = "Subnets for the Studio domain. Must have a route to an IGW or NAT."
  type        = list(string)

  validation {
    condition     = length(var.public_subnet_ids) > 0
    error_message = "public_subnet_ids must not be empty."
  }
}


# ##############################
# Space: Notebook
# ##############################
variable "notebook_instance_type" {
  description = "Default instance type for the JupyterLab app in a space."
  type        = string
  default     = "ml.t3.xlarge"
}

variable "notebook_volume_size" {
  description = "Size in GB of the space EBS volume."
  type        = number
  default     = 10

  validation {
    condition     = var.notebook_volume_size >= 5 && var.notebook_volume_size <= 16384
    error_message = "space_volume_size must be between 5 and 16384 GB."
  }
}

# ##############################
# MLflow
# ##############################
variable "mlflow_tracking_server_size" {
  description = "Tracking server size. Small is the cheapest."
  type        = string
  default     = "Small"

  validation {
    condition     = contains(["Small", "Medium", "Large"], var.mlflow_tracking_server_size)
    error_message = "mlflow_tracking_server_size must be Small, Medium or Large."
  }
}

variable "mlflow_version" {
  description = "MLflow version the tracking server runs."
  type        = string
  default     = "3.0"
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
