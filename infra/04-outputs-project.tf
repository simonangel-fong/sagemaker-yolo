# outputs-project.tf

# ##############################
# S3
# ##############################
output "s3_bucket_name" {
  value = aws_s3_bucket.yolo.id
}

output "s3_sync_command" {
  value = "aws s3 sync data/raw s3://${aws_s3_bucket.yolo.id}/raw-data/"
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

# ##############################
# ECR
# ##############################
output "ecr_train_repo" {
  value = aws_ecr_repository.train.repository_url
}

output "ecr_lambda_repo" {
  value = aws_ecr_repository.lambda.repository_url
}

# ##############################
# CI/CD
# ##############################
# Store this as the AWS_ROLE_ARN secret (or variable) in the GitHub repository.
output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}
