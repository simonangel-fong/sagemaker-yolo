# variables.tf

# ##############################
# Metadata
# ##############################
variable "project" {
  description = "Project name"
}

variable "env" {
  description = "Environmet"
}

variable "git_repository_url" {
  description = "HTTPS URL offered in the JupyterLab clone menu."
  type        = string
}

variable "github_repository" {
  description = "GitHub repository in owner/name form, trusted by the CI OIDC role."
  type        = string
}

# ##############################
# Providers: aws
# ##############################
variable "aws_region" {
  description = "AWS region"
}
