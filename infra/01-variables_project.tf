# variables.tf

# ##############################
# Metadata
# ##############################
variable "env" {
  description = "Environmet"
}

# tf backend bucket
variable "tf_state_bucket" {
  description = "S3 bucket holding the terraform state."
  type        = string
}

variable "github_owner_id" {
  description = "GitHub repo owner id"
}

variable "github_repo_id" {
  description = "GitHub repo id"
}

# ##############################
# Providers: aws
# ##############################
variable "aws_region" {
  description = "AWS region"
}

