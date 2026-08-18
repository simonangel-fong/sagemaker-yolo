# s3.tf

locals {
  s3_content_types = {
    ".html" = "text/html"
    ".css"  = "text/css"
    ".js"   = "text/javascript"
    ".png"  = "image/png"
    ".jpg"  = "image/jpeg"
    ".jpeg" = "image/jpeg"
    ".gif"  = "image/gif"
    ".svg"  = "image/svg+xml"
    ".ico"  = "image/x-icon"
    ".mp4"  = "video/mp4"
  }

  s3_web_files = fileset("${path.module}/../web", "**/*.{html,css,js,png,jpg,jpeg,gif,svg,ico,mp4}")
}

# upload object
resource "aws_s3_object" "web" {
  for_each = var.enable_deploy ? local.s3_web_files : []

  bucket       = aws_s3_bucket.yolo.id
  key          = "web/${each.value}"
  source       = "${path.module}/../web/${each.value}"
  source_hash  = filemd5("${path.module}/../web/${each.value}")
  content_type = lookup(local.s3_content_types, regex("\\.[^.]+$", each.value), "application/octet-stream")
}

# ##############################
# S3: OAC
# ##############################
resource "aws_cloudfront_origin_access_control" "web" {
  count = var.enable_deploy ? 1 : 0

  name                              = "${local.prefix_name}-web-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}
