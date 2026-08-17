# lambda-monitor.tf

# ##############################
# Lambda: log
# ##############################
resource "aws_cloudwatch_log_group" "lambda" {
  count = var.enable_deploy ? 1 : 0

  name              = "/aws/lambda/${aws_lambda_function.lambda[0].function_name}"
  retention_in_days = 14
  tags              = local.default_tags
}

# ##############################
# Lambda alarms
# ##############################
# error
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  count = var.enable_deploy ? 1 : 0

  alarm_name        = "${local.prefix_name}-lambda-errors"
  alarm_description = "The predict function failed. Check the lambda log group."

  namespace   = "AWS/Lambda"
  metric_name = "Errors"
  statistic   = "Sum"

  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.lambda[0].function_name
  }

  alarm_actions = [aws_sns_topic.alerts[0].arn]
  ok_actions    = [aws_sns_topic.alerts[0].arn]
}

# throttles
resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  count = var.enable_deploy ? 1 : 0

  alarm_name        = "${local.prefix_name}-lambda-throttles"
  alarm_description = "The predict function hit a concurrency limit."

  namespace   = "AWS/Lambda"
  metric_name = "Throttles"
  statistic   = "Sum"

  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.lambda[0].function_name
  }

  alarm_actions = [aws_sns_topic.alerts[0].arn]
  ok_actions    = [aws_sns_topic.alerts[0].arn]
}

# duration
resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  count = var.enable_deploy ? 1 : 0

  alarm_name        = "${local.prefix_name}-lambda-duration"
  alarm_description = "The predict function is approaching its 30s timeout, usually waiting on an endpoint cold start."

  namespace          = "AWS/Lambda"
  metric_name        = "Duration"
  extended_statistic = "p95"

  period              = 300
  evaluation_periods  = 2
  threshold           = local.alarm_lambda_duration_ms
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.lambda[0].function_name
  }

  alarm_actions = [aws_sns_topic.alerts[0].arn]
  ok_actions    = [aws_sns_topic.alerts[0].arn]
}

# invocation spike
resource "aws_cloudwatch_metric_alarm" "lambda_invocation_spike" {
  count = var.enable_deploy ? 1 : 0

  alarm_name        = "${local.prefix_name}-lambda-invocation-spike"
  alarm_description = "Unusual invocation volume on an unauthenticated function URL. Check for abuse before it bills through to the endpoint."

  namespace   = "AWS/Lambda"
  metric_name = "Invocations"
  statistic   = "Sum"

  period              = 300
  evaluation_periods  = 1
  threshold           = local.alarm_lambda_invocations_5min
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.lambda[0].function_name
  }

  alarm_actions = [aws_sns_topic.alerts[0].arn]
}

# Application errors
resource "aws_cloudwatch_log_metric_filter" "lambda_app_errors" {
  count = var.enable_deploy ? 1 : 0

  name           = "${local.prefix_name}-lambda-app-errors"
  log_group_name = aws_cloudwatch_log_group.lambda[0].name
  pattern        = "?ERROR ?Exception ?Traceback"

  metric_transformation {
    name          = "ApplicationErrors"
    namespace     = "${local.project_name}/${var.env}"
    value         = "1"
    default_value = "0"
  }
}

# app errors
resource "aws_cloudwatch_metric_alarm" "lambda_app_errors" {
  count = var.enable_deploy ? 1 : 0

  alarm_name        = "${local.prefix_name}-lambda-app-errors"
  alarm_description = "Errors logged by the predict handler that did not surface as lambda invocation failures."

  namespace   = "${local.project_name}/${var.env}"
  metric_name = aws_cloudwatch_log_metric_filter.lambda_app_errors[0].metric_transformation[0].name
  statistic   = "Sum"

  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alerts[0].arn]
}