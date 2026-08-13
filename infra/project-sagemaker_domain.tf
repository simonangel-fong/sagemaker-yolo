# sagemaker_domain.tf

# ##############################
# Lifecycle config: JupyterLab 
# ##############################
resource "aws_sagemaker_studio_lifecycle_config" "clone_repo" {
  studio_lifecycle_config_name     = "${local.prefix_name}-clone-repo"
  studio_lifecycle_config_app_type = "JupyterLab"

  # init notebook instance
  studio_lifecycle_config_content = base64encode(
    templatefile("${path.module}/scripts/notebook-init.sh", {
      repo_url    = var.git_repository_url
      bucket_name = aws_s3_bucket.yolo.id
    })
  )
}

# ##############################
# Sagemaker Studio Domain
# ##############################
resource "aws_sagemaker_domain" "yolo" {
  domain_name = local.prefix_name
  auth_mode   = "IAM"

  # Network
  vpc_id                  = var.vpc_id
  subnet_ids              = var.public_subnet_ids
  app_network_access_type = "PublicInternetOnly"

  # security
  kms_key_id = aws_kms_key.yolo.arn

  # apps
  default_user_settings {
    execution_role = aws_iam_role.sagemaker_execution.arn

    # notebook
    jupyter_lab_app_settings {
      default_resource_spec {
        instance_type = var.notebook_instance_type
      }

      lifecycle_config_arns = [aws_sagemaker_studio_lifecycle_config.clone_repo.arn]
    }
  }

  # drop the EFS volume on destroy
  retention_policy {
    home_efs_file_system = "Delete"
  }
}

# ##############################
# User profile
# ##############################
resource "aws_sagemaker_user_profile" "admin" {
  user_profile_name = "${local.prefix_name}-admin"
  domain_id         = aws_sagemaker_domain.yolo.id

  user_settings {
    execution_role = aws_iam_role.sagemaker_execution.arn
  }
}
