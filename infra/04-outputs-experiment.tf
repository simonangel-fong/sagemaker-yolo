# outputs-experiment.tf

output "studio_login_command" {
  description = "CLI command that returns a presigned Studio URL for alice."
  value       = var.enable_experiment ? "aws sagemaker create-presigned-domain-url --domain-id ${aws_sagemaker_domain.yolo.id} --user-profile-name ${aws_sagemaker_user_profile.admin.user_profile_name} --region ${var.aws_region} --query AuthorizedUrl --output text" : null
}

# ##############################
# Notebook
# ##############################
output "notebook_url" {
  value = one(aws_sagemaker_space.notebook[*].url)
}

