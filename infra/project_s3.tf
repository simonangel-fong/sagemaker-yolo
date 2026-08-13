# # s3.tf

# locals {
#   bucket_name = "${local.prefix_name}-${random_string.suffix.result}"
#   bucket_prefix = [
#     "raw_data",   # raw data
#     "notebook",   # notebook
#     "mlflow",     # mlflow
#     "inference/", # inference artifacts
#     "web/",       # web artifacts
#   ]
# }

# resource "random_string" "suffix" {
#   length  = 6
#   special = false
#   upper   = false
# }

# # ##############################
# # S3
# # ##############################
# resource "aws_s3_bucket" "yolo" {
#   bucket        = local.bucket_name
#   force_destroy = true
# }

# # prefixes keys
# resource "aws_s3_object" "prefixes" {
#   for_each = toset(local.bucket_prefix)

#   bucket = aws_s3_bucket.yolo.id
#   key    = each.value
# }

# # version
# resource "aws_s3_bucket_versioning" "yolo" {
#   bucket = aws_s3_bucket.yolo.id

#   versioning_configuration {
#     status = "Enabled"
#   }
# }

# # ##############################
# # Lifecycle
# # ##############################
# # Versioning 
# resource "aws_s3_bucket_lifecycle_configuration" "yolo" {
#   bucket = aws_s3_bucket.yolo.id

#   # abort failed multipart uploads
#   rule {
#     id     = "abort-incomplete-multipart"
#     status = "Enabled"

#     filter {}

#     abort_incomplete_multipart_upload {
#       days_after_initiation = 7
#     }
#   }

#   rule {
#     id     = "expire-noncurrent-versions"
#     status = "Enabled"

#     filter {}

#     noncurrent_version_expiration {
#       noncurrent_days = 30
#     }
#   }

#   # archive in 90
#   rule {
#     id     = "archive-raw-data"
#     status = "Enabled"

#     filter {
#       prefix = "data/raw/"
#     }

#     transition {
#       days          = 90
#       storage_class = "STANDARD_IA"
#     }
#   }

#   depends_on = [aws_s3_bucket_versioning.yolo]
# }


# # ##############################
# # S3 security
# # ##############################
# # block public
# resource "aws_s3_bucket_public_access_block" "yolo" {
#   bucket = aws_s3_bucket.yolo.id

#   block_public_acls       = true
#   block_public_policy     = true
#   ignore_public_acls      = true
#   restrict_public_buckets = true
# }

# # encryption
# resource "aws_s3_bucket_server_side_encryption_configuration" "yolo" {
#   bucket = aws_s3_bucket.yolo.id

#   rule {
#     apply_server_side_encryption_by_default {
#       sse_algorithm     = "aws:kms"
#       kms_master_key_id = aws_kms_key.yolo.arn
#     }
#     bucket_key_enabled = true
#   }
# }

# # ##############################
# # Bucket policy
# # ##############################
# # SSE covers encryption at rest; this covers in transit.
# data "aws_iam_policy_document" "yolo_bucket" {
#   statement {
#     sid       = "DenyInsecureTransport"
#     effect    = "Deny"
#     actions   = ["s3:*"]
#     resources = [aws_s3_bucket.yolo.arn, "${aws_s3_bucket.yolo.arn}/*"]

#     principals {
#       type        = "*"
#       identifiers = ["*"]
#     }

#     condition {
#       test     = "Bool"
#       variable = "aws:SecureTransport"
#       values   = ["false"]
#     }
#   }

#   # allow cloudfront to access web bucket
#   dynamic "statement" {
#     for_each = var.enable_deploy ? [1] : []

#     content {
#       sid       = "AllowCloudFrontReadWeb"
#       effect    = "Allow"
#       actions   = ["s3:GetObject"]
#       resources = ["${aws_s3_bucket.yolo.arn}/web/*"]

#       principals {
#         type        = "Service"
#         identifiers = ["cloudfront.amazonaws.com"]
#       }

#       condition {
#         test     = "StringEquals"
#         variable = "AWS:SourceArn"
#         values   = [aws_cloudfront_distribution.web[0].arn]
#       }
#     }
#   }
# }

# resource "aws_s3_bucket_policy" "yolo" {
#   bucket = aws_s3_bucket.yolo.id
#   policy = data.aws_iam_policy_document.yolo_bucket.json

#   depends_on = [aws_s3_bucket_public_access_block.yolo]
# }
