# cloudwatch-dashboard.tf

# ##############################
# Dashboard
# ##############################
resource "aws_cloudwatch_dashboard" "main" {
  count = var.enable_deploy ? 1 : 0

  dashboard_name = local.prefix_name

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Endpoint invocations"
          region = var.aws_region
          view   = "timeSeries"
          period = 300
          stat   = "Sum"
          # These are only published with the VariantName dimension; querying
          # EndpointName alone matches no metric. Serverless endpoints do not
          # emit InvocationsThrottled at all.
          metrics = [
            ["AWS/SageMaker", "Invocations", "EndpointName", aws_sagemaker_endpoint.yolo[0].name, "VariantName", "AllTraffic"],
            [".", "Invocation4XXErrors", ".", ".", ".", "."],
            [".", "Invocation5XXErrors", ".", ".", ".", "."],
            [".", "ServerlessConcurrentExecutionsUtilization", ".", ".", ".", ".", { stat = "Maximum", yAxis = "right" }],
          ]
          yAxis = {
            right = { label = "concurrency used", showUnits = false, min = 0, max = 1 }
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Endpoint latency"
          region = var.aws_region
          view   = "timeSeries"
          period = 300
          stat   = "p99"
          metrics = [
            ["AWS/SageMaker", "ModelLatency", "EndpointName", aws_sagemaker_endpoint.yolo[0].name, "VariantName", "AllTraffic"],
            [".", "OverheadLatency", ".", ".", ".", "."],
          ]
          yAxis = {
            left = { label = "microseconds", showUnits = false }
          }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Predict lambda"
          region = var.aws_region
          view   = "timeSeries"
          period = 300
          stat   = "Sum"
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.lambda[0].function_name],
            [".", "Errors", ".", "."],
            [".", "Throttles", ".", "."],
            [".", "ConcurrentExecutions", ".", ".", { stat = "Maximum" }],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Predict lambda duration"
          region = var.aws_region
          view   = "timeSeries"
          period = 300
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.lambda[0].function_name, { stat = "p50" }],
            ["...", { stat = "p95" }],
            ["...", { stat = "Maximum" }],
          ]
          yAxis = {
            left = { label = "milliseconds", showUnits = false }
          }
          annotations = {
            horizontal = [
              { label = "timeout", value = 30000 },
            ]
          }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 24
        height = 6
        properties = {
          title = "CloudFront"
          # CloudFront metrics only exist in us-east-1.
          region = "us-east-1"
          view   = "timeSeries"
          period = 300
          metrics = [
            ["AWS/CloudFront", "Requests", "DistributionId", aws_cloudfront_distribution.web[0].id, "Region", "Global", { stat = "Sum" }],
            [".", "4xxErrorRate", ".", ".", ".", ".", { stat = "Average", yAxis = "right" }],
            [".", "5xxErrorRate", ".", ".", ".", ".", { stat = "Average", yAxis = "right" }],
          ]
          yAxis = {
            right = { label = "percent", showUnits = false }
          }
        }
      },
    ]
  })
}
