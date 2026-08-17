# cloudfront-monitor.tf

resource "aws_cloudwatch_metric_alarm" "cloudfront_5xx" {
  count    = var.enable_deploy ? 1 : 0
  provider = aws.us_east_1

  alarm_name        = "${local.prefix_name}-cloudfront-5xx"
  alarm_description = "CloudFront is serving server errors, from either the s3-web or lambda origin."

  namespace   = "AWS/CloudFront"
  metric_name = "5xxErrorRate"
  statistic   = "Average"

  # Percentage of requests, not a count.
  period              = 300
  evaluation_periods  = 2
  threshold           = 5
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    DistributionId = aws_cloudfront_distribution.web[0].id
    Region         = "Global"
  }

  alarm_actions = [aws_sns_topic.alerts_cloudfront[0].arn]
  ok_actions    = [aws_sns_topic.alerts_cloudfront[0].arn]
}
