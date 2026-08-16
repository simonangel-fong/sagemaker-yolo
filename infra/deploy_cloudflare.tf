# cloudflare.tf

# Certificate
data "aws_acm_certificate" "web" {
  count = var.enable_deploy ? 1 : 0

  provider = aws.us_east_1

  domain      = local.acm_certificate_domain
  statuses    = ["ISSUED"]
  most_recent = true
}

# ##############################
# DNS record
# ##############################
resource "cloudflare_dns_record" "web" {
  count = var.enable_deploy ? 1 : 0

  zone_id = var.cloudflare_zone_id
  name    = var.web_domain
  type    = "CNAME"
  content = aws_cloudfront_distribution.web[0].domain_name
  ttl     = 300
  proxied = false

  comment = "CloudFront distribution for the YOLO web app"
}
