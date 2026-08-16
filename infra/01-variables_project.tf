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

  validation {
    condition     = length(split("/", var.github_repository)) == 2
    error_message = "github_repository must be in owner/name form."
  }
}

# Repositories created on or after 2026-07-15 emit an immutable OIDC subject
# claim carrying these permanent numeric IDs. Read them with:
#   gh api repos/<owner>/<name> --jq '{repo: .id, owner: .owner.id}'
variable "github_owner_id" {
  description = "Permanent numeric ID of the GitHub account owning the repository."
  type        = string
}

variable "github_repository_id" {
  description = "Permanent numeric ID of the GitHub repository."
  type        = string
}

# ##############################
# Providers: aws
# ##############################
variable "aws_region" {
  description = "AWS region"
}
