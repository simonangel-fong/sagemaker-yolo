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
