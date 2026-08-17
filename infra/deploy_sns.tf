# deploy_sns.tf

# ##############################
# SNS topic: lambda & endpoint
# ##############################
resource "aws_sns_topic" "alerts" {
  count = var.enable_deploy ? 1 : 0

  name              = "${local.project_name}-alerts"
  display_name      = "AppAlerts"
  kms_master_key_id = aws_kms_alias.yolo.id
}

# subscription
resource "aws_sns_topic_subscription" "alerts_email" {
  count = var.enable_deploy ? 1 : 0

  topic_arn = aws_sns_topic.alerts[0].arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ##############################
# SNS topic: cloudfront
# ##############################
# CloudFront: us-east-1
resource "aws_sns_topic" "alerts_cloudfront" {
  count = var.enable_deploy ? 1 : 0

  name              = "${local.prefix_name}-alerts"
  provider          = aws.us_east_1
  kms_master_key_id = aws_kms_alias.yolo.id
}

resource "aws_sns_topic_subscription" "alerts_cloudfront" {
  count    = var.enable_deploy ? 1 : 0
  provider = aws.us_east_1

  topic_arn = aws_sns_topic.alerts_cloudfront[0].arn
  protocol  = "email"
  endpoint  = var.alert_email
}
