# lambda.tf

# Image
data "aws_ecr_image" "predict" {
  count = var.enable_deploy ? 1 : 0

  repository_name = "${var.project}-predict"
  image_tag       = var.lambda_image_tag
}

# ##############################
# IAM
# ##############################
resource "aws_iam_role" "lambda_predict" {
  count = var.enable_deploy ? 1 : 0

  name = "${local.prefix_name}-lambda-predict-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  count = var.enable_deploy ? 1 : 0

  role       = aws_iam_role.lambda_predict[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Scoped to the one endpoint
data "aws_iam_policy_document" "lambda_invoke_endpoint" {
  count = var.enable_deploy ? 1 : 0

  statement {
    sid       = "InvokeYoloEndpoint"
    effect    = "Allow"
    actions   = ["sagemaker:InvokeEndpoint"]
    resources = [aws_sagemaker_endpoint.yolo[0].arn]
  }
}

resource "aws_iam_policy" "lambda_invoke_endpoint" {
  count = var.enable_deploy ? 1 : 0

  name        = "${local.prefix_name}-lambda-invoke-endpoint"
  description = "Invoke the YOLO inference endpoint."
  policy      = data.aws_iam_policy_document.lambda_invoke_endpoint[0].json
}

resource "aws_iam_role_policy_attachment" "lambda_invoke_endpoint" {
  count = var.enable_deploy ? 1 : 0

  role       = aws_iam_role.lambda_predict[0].name
  policy_arn = aws_iam_policy.lambda_invoke_endpoint[0].arn
}

# ##############################
# Function
# ##############################
resource "aws_lambda_function" "predict" {
  count = var.enable_deploy ? 1 : 0

  function_name = "${local.prefix_name}-predict"
  role          = aws_iam_role.lambda_predict[0].arn

  package_type = "Image"
  image_uri    = data.aws_ecr_image.predict[0].image_uri
  timeout      = 30
  memory_size  = 1024

  # env var
  environment {
    variables = {
      ENDPOINT_NAME = aws_sagemaker_endpoint.yolo[0].name
      MODEL_NAME    = local.web_model_name
      IMGSZ         = "640"
      CLASSES       = jsonencode(["car_plate"])
      ALLOW_ORIGIN  = local.web_allow_origin
    }
  }

  tags = local.default_tags
}

resource "aws_cloudwatch_log_group" "predict" {
  count = var.enable_deploy ? 1 : 0

  name              = "/aws/lambda/${aws_lambda_function.predict[0].function_name}"
  retention_in_days = 14
  tags              = local.default_tags
}

# ##############################
# Function URL
# ##############################
resource "aws_lambda_function_url" "predict" {
  count = var.enable_deploy ? 1 : 0

  function_name      = aws_lambda_function.predict[0].function_name
  authorization_type = "NONE"
}
