# # outputs.tf

# # ##############################
# # S3
# # ##############################
# output "s3_bucket_name" {
#   value = aws_s3_bucket.yolo.id
# }

# output "s3_sync_command" {
#   value = "aws s3 sync data/raw s3://${aws_s3_bucket.yolo.id}/data/raw"
# }

# # ##############################
# # Studio
# # ##############################
# output "studio_domain_role_arn" {
#   value = aws_iam_role.sagemaker_execution.arn
# }

# output "studio_domain_id" {
#   value = one(aws_sagemaker_domain.yolo[*].id)
# }

# output "studio_login_command" {
#   description = "CLI command that returns a presigned Studio URL for alice."
#   value       = var.enable_experiment ? "aws sagemaker create-presigned-domain-url --domain-id ${aws_sagemaker_domain.yolo[0].id} --user-profile-name ${aws_sagemaker_user_profile.admin[0].user_profile_name} --region ${var.aws_region} --query AuthorizedUrl --output text" : null
# }

# # ##############################
# # Notebook
# # ##############################
# output "notebook_url" {
#   value = one(aws_sagemaker_space.notebook[*].url)
# }

# # ##############################
# # MLflow
# # ##############################
# output "mlflow_tracking_server_arn" {
#   description = "Tracking URI for mlflow.set_tracking_uri()."
#   value       = one(aws_sagemaker_mlflow_tracking_server.yolo[*].arn)
# }

# output "mlflow_tracking_server_url" {
#   description = "MLflow UI URL. Requires a presigned URL to open."
#   value       = one(aws_sagemaker_mlflow_tracking_server.yolo[*].tracking_server_url)
# }

# output "mlflow_ui_command" {
#   description = "CLI command that returns a presigned MLflow UI URL."
#   value       = var.enable_experiment ? "aws sagemaker create-presigned-mlflow-tracking-server-url --tracking-server-name ${aws_sagemaker_mlflow_tracking_server.yolo[0].tracking_server_name} --region ${var.aws_region} --query AuthorizedUrl --output text" : null
# }

# # ##############################
# # Endpoint
# # ##############################
# output "endpoint_name" {
#   description = "Target for invoke_endpoint()."
#   value       = one(aws_sagemaker_endpoint.yolo[*].name)
# }

# output "endpoint_model_data_url" {
#   description = "Tarball the endpoint serves. Rebuild with deploy/package.py."
#   value       = one(aws_sagemaker_model.yolo[*].primary_container[0].model_data_url)
# }

# output "endpoint_smoke_test_command" {
#   description = "Invoke the endpoint with a single image."
#   value       = var.enable_deploy ? "python -m deploy.invoke --image data/raw/audi_a5_with_license_plate_43.png" : null
# }

# # ##############################
# # Web app
# # ##############################
# output "web_url" {
#   description = "The deployed web app."
#   value       = var.enable_deploy ? "https://${var.web_domain}" : null
# }

# output "web_cloudfront_domain" {
#   description = "Distribution domain the custom domain points at."
#   value       = one(aws_cloudfront_distribution.web[*].domain_name)
# }

# output "lambda_function_url" {
#   description = "Predict function, direct. CloudFront proxies this at /v1/*."
#   value       = one(aws_lambda_function_url.predict[*].function_url)
# }

# output "web_readiness_command" {
#   description = "Check the predict route through CloudFront."
#   value       = var.enable_deploy ? "curl https://${var.web_domain}/v1/models/${var.web_model_name}" : null
# }
