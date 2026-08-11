# outputs.tf

# ##############################
# S3
# ##############################
output "s3_bucket_name" {
  value = aws_s3_bucket.yolo.id
}

output "s3_sync_command" {
  value = "aws s3 sync data/raw s3://${aws_s3_bucket.yolo.id}/data/raw"
}

# ##############################
# Studio
# ##############################
output "studio_domain_role_arn" {
  value = aws_iam_role.sagemaker_execution.arn
}

output "studio_domain_id" {
  value = aws_sagemaker_domain.yolo.id
}

output "studio_login_command" {
  description = "CLI command that returns a presigned Studio URL for alice."
  value       = "aws sagemaker create-presigned-domain-url --domain-id ${aws_sagemaker_domain.yolo.id} --user-profile-name ${aws_sagemaker_user_profile.admin.user_profile_name} --region ${var.aws_region} --query AuthorizedUrl --output text"
}

# ##############################
# Notebook
# ##############################
output "notebook_url" {
  value = aws_sagemaker_space.notebook.url
}

# ##############################
# MLflow
# ##############################
output "mlflow_tracking_server_arn" {
  description = "Tracking URI for mlflow.set_tracking_uri()."
  value       = aws_sagemaker_mlflow_tracking_server.yolo.arn
}

output "mlflow_tracking_server_url" {
  description = "MLflow UI URL. Requires a presigned URL to open."
  value       = aws_sagemaker_mlflow_tracking_server.yolo.tracking_server_url
}

output "mlflow_ui_command" {
  description = "CLI command that returns a presigned MLflow UI URL."
  value       = "aws sagemaker create-presigned-mlflow-tracking-server-url --tracking-server-name ${aws_sagemaker_mlflow_tracking_server.yolo.tracking_server_name} --region ${var.aws_region} --query AuthorizedUrl --output text"
}
