# # outputs-deploy.tf

# # ##############################
# # Sagemaker Endpoint
# # ##############################
# output "sagemaker_endpoint_name" {
#   description = "Target for invoke_endpoint()."
#   value       = one(aws_sagemaker_endpoint.yolo[*].name)
# }

# output "sagemaker_endpoint_smoke_test_command" {
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
#   value       = var.enable_deploy ? "curl https://${var.web_domain}/v1/models/${local.web_model_name}" : null
# }
