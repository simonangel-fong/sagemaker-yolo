# cloudflare.tf

# ##############################
# Certificate
# ##############################
# Pre-existing wildcard, not managed here: *.arguswatcher.net already covers
# this subdomain, so there is nothing to issue or DNS-validate.
#
# us-east-1 because CloudFront reads certificates only from that region.
# statuses filters deliberately: the zone also has expired per-subdomain certs,
# and an unfiltered lookup could match one of those.
data "aws_acm_certificate" "web" {
  count = var.enable_deploy ? 1 : 0

  provider = aws.us_east_1

  domain      = var.acm_certificate_domain
  statuses    = ["ISSUED"]
  most_recent = true
}

# ##############################
# App record
# ##############################
# DNS-only. Proxying would put Cloudflare in front of CloudFront, adding a TLS
# hop and a body limit while duplicating caching the distribution already does.
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
