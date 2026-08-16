# cloudfront.tf

# ##############################
# Cache policies
# ##############################
data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

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

  # web
  origin {
    origin_id                = "s3-web"
    domain_name              = aws_s3_bucket.yolo.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.web[0].id
    origin_path              = "/web"
  }

  # predict
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

  # cache web
  default_cache_behavior {
    target_origin_id       = "s3-web"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
  }

  # cache inference
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
