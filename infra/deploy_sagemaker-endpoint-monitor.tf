# sagemaker-endpoint-monitor.tf

# ##############################
# Endpoint: Log
# ##############################
resource "aws_cloudwatch_log_group" "sagemaker_endpoint" {
  count = var.enable_deploy ? 1 : 0

  name              = "/aws/sagemaker/Endpoints/${local.prefix_name}"
  retention_in_days = local.monitoring_log_retention_days
}

# ##############################
# Endpoint: alarms
# ##############################
# 5xx
resource "aws_cloudwatch_metric_alarm" "endpoint_5xx" {
  count = var.enable_deploy ? 1 : 0

  alarm_name        = "${local.prefix_name}-endpoint-5xx"
  alarm_description = "The model container returned a server error."

  namespace   = "AWS/SageMaker"
  metric_name = "Invocation5XXErrors"
  statistic   = "Sum"

  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"

  # No invocations means no datapoints, which is healthy, not unknown.
  treat_missing_data = "notBreaching"

  # VariantName is required: the invocation metrics are not published against
  # EndpointName alone, so omitting it makes the alarm match no data and,
  # with notBreaching, sit permanently OK.
  dimensions = {
    EndpointName = aws_sagemaker_endpoint.yolo[0].name
    VariantName  = "AllTraffic"
  }

  alarm_actions = [aws_sns_topic.alerts[0].arn]
  ok_actions    = [aws_sns_topic.alerts[0].arn]
}

# 4xx
resource "aws_cloudwatch_metric_alarm" "endpoint_4xx" {
  count = var.enable_deploy ? 1 : 0

  alarm_name        = "${local.prefix_name}-endpoint-4xx"
  alarm_description = "The endpoint rejected requests."

  namespace   = "AWS/SageMaker"
  metric_name = "Invocation4XXErrors"
  statistic   = "Sum"

  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    EndpointName = aws_sagemaker_endpoint.yolo[0].name
    VariantName  = "AllTraffic"
  }

  alarm_actions = [aws_sns_topic.alerts[0].arn]
  ok_actions    = [aws_sns_topic.alerts[0].arn]
}

# latency
resource "aws_cloudwatch_metric_alarm" "endpoint_latency" {
  count = var.enable_deploy ? 1 : 0

  alarm_name        = "${local.prefix_name}-endpoint-latency"
  alarm_description = "Model latency p99 is high."

  namespace          = "AWS/SageMaker"
  metric_name        = "ModelLatency"
  extended_statistic = "p99"

  # ModelLatency is published in microseconds.
  period              = 300
  evaluation_periods  = 2
  threshold           = local.alarm_endpoint_latency_ms * 1000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    EndpointName = aws_sagemaker_endpoint.yolo[0].name
    VariantName  = "AllTraffic"
  }

  alarm_actions = [aws_sns_topic.alerts[0].arn]
  ok_actions    = [aws_sns_topic.alerts[0].arn]
}

# concurrency saturation: max_concurrency is 5
# Serverless endpoints do not publish InvocationsThrottled; they report
# saturation through ServerlessConcurrentExecutionsUtilization, a 0-1 fraction
# of MaxConcurrency. Alarm before saturation so there is warning ahead of the
# throttling itself.
resource "aws_cloudwatch_metric_alarm" "endpoint_throttled" {
  count = var.enable_deploy ? 1 : 0

  alarm_name        = "${local.prefix_name}-endpoint-concurrency"
  alarm_description = "Endpoint is nearing its serverless concurrency limit; requests risk throttling."

  namespace   = "AWS/SageMaker"
  metric_name = "ServerlessConcurrentExecutionsUtilization"
  statistic   = "Maximum"

  period              = 300
  evaluation_periods  = 1
  threshold           = 0.8
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    EndpointName = aws_sagemaker_endpoint.yolo[0].name
    VariantName  = "AllTraffic"
  }

  alarm_actions = [aws_sns_topic.alerts[0].arn]
  ok_actions    = [aws_sns_topic.alerts[0].arn]
}
