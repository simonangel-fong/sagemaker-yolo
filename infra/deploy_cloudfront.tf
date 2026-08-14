# cloudfront.tf

# ##############################
# Web assets
# ##############################
# Uploaded from terraform rather than a separate sync step so the distribution
# and the files it serves stay in one apply. content_type is set per extension
# because S3 defaults to binary/octet-stream, which the browser will not render.
locals {
  web_content_types = {
    ".html" = "text/html"
    ".css"  = "text/css"
    ".js"   = "text/javascript"
  }

  web_files = fileset("${path.module}/../web", "**/*.{html,css,js}")
}

resource "aws_s3_object" "web" {
  for_each = var.enable_deploy ? local.web_files : []

  bucket       = aws_s3_bucket.yolo.id
  key          = "web/${each.value}"
  source       = "${path.module}/../web/${each.value}"
  etag         = filemd5("${path.module}/../web/${each.value}")
  content_type = lookup(local.web_content_types, regex("\\.[^.]+$", each.value), "application/octet-stream")
}

# ##############################
# Origin access
# ##############################
# OAC, not public read: the bucket stays private and CloudFront signs its
# origin requests, so the S3 objects are only reachable through the
# distribution.
resource "aws_cloudfront_origin_access_control" "web" {
  count = var.enable_deploy ? 1 : 0

  name                              = "${local.prefix_name}-web-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ##############################
# Cache policies
# ##############################
# The predict call is a POST with a body that must reach the function intact,
# so nothing about it may be cached or the second detection would return the
# first image's boxes.
data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

# Host must be excluded: forwarding the CloudFront host to a Lambda Function
# URL breaks its SigV4 host check and returns 403.
data "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

# ##############################
# Distribution
# ##############################
resource "aws_cloudfront_distribution" "web" {
  count = var.enable_deploy ? 1 : 0

  enabled             = true
  default_root_object = "index.html"
  comment             = "${local.prefix_name} yolo web app"
  price_class         = "PriceClass_100"

  aliases = [var.web_domain]

  origin {
    origin_id                = "s3-web"
    domain_name              = aws_s3_bucket.yolo.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.web[0].id
    origin_path              = "/web"
  }

  origin {
    origin_id   = "lambda-predict"
    domain_name = replace(replace(aws_lambda_function_url.predict[0].function_url, "https://", ""), "/", "")

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "s3-web"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
  }

  # main.js calls /v1/models/... same-origin, so this path routes to the
  # function and the browser never sees a cross-origin request
  ordered_cache_behavior {
    path_pattern           = "/v1/*"
    target_origin_id       = "lambda-predict"
    viewer_protocol_policy = "https-only"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]

    cache_policy_id          = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = data.aws_acm_certificate.web[0].arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = local.default_tags
}
