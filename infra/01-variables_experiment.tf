# variables.tf

# ##############################
# Control
# ##############################
variable "enable_experiment" {
  description = "Whether to enable studio notebook space and MLflow tracking server."
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
