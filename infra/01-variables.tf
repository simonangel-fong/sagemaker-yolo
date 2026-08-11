# variables.tf

# ##############################
# Metadata
# ##############################
variable "project" {
  default = "sagemaker-yolo"
}

variable "env" {
  default = "dev"
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
  default     = 5

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
