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
  }

  # An extension must appear in both this fileset and s3_content_types above,
  # or the object either never uploads or is served as octet-stream.
  s3_web_files = fileset("${path.module}/../web", "**/*.{html,css,js,png,jpg,jpeg,gif,svg,ico}")
}

# upload object
resource "aws_s3_object" "web" {
  for_each = var.enable_deploy ? local.s3_web_files : []

  bucket       = aws_s3_bucket.yolo.id
  key          = "web/${each.value}"
  source       = "${path.module}/../web/${each.value}"
  etag         = filemd5("${path.module}/../web/${each.value}")
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
