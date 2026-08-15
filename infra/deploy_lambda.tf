# lambda.tf

# ##############################
# Image
# ##############################
# The image is built and pushed outside Terraform (see docs/04-deploy.md), so
# this only resolves the tag to a digest. Pinning the digest rather than the
# tag is what makes `terraform apply` redeploy the function when a new image is
# pushed to the same tag -- otherwise the tag string never changes and
# Terraform sees no diff.
#
# repository_name is the literal name rather than aws_ecr_repository.predict.name
# on purpose. The repo is KMS-encrypted, and that key's policy references the
# CloudFront distribution, which fronts this very function -- reading the name
# off the resource closes that loop into a dependency cycle. The push has to
# happen before apply regardless, so the repo already exists by then.
data "aws_ecr_image" "predict" {
  count = var.enable_deploy ? 1 : 0

  repository_name = "${var.project}-predict"
  image_tag       = var.predict_image_tag
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

# Scoped to the one endpoint: this function has no reason to reach any other
# SageMaker resource, and SageMakerFullAccess on an internet-facing function
# would be a much larger blast radius than the job needs.
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

  # handler and runtime are set by the Dockerfile's CMD, and are rejected here
  # for an image-based function
  # composed from the data source, not aws_ecr_repository.predict, for the same
  # cycle reason noted above
  package_type = "Image"
  image_uri    = data.aws_ecr_image.predict[0].image_uri

  # the endpoint itself can take ~5s on a cold start, so the default 3s would
  # time out the first request of the day rather than the model failing.
  # A container cold start also has to pull the image, so this is now the
  # floor rather than a generous margin.
  timeout = 30

  # 512 MB was sized for a zip that only held boto3; the container also loads
  # FastAPI, Starlette and Pydantic on cold start
  memory_size = 1024

  environment {
    variables = {
      ENDPOINT_NAME = aws_sagemaker_endpoint.yolo[0].name
      MODEL_NAME    = var.web_model_name
      IMGSZ         = "640"
      CLASSES       = jsonencode(["car_plate"])
      ALLOW_ORIGIN  = var.allow_origin
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
# NONE auth: CloudFront fronts this and the browser cannot sign SigV4. The
# function is a thin wrapper over one endpoint and returns no data the page
# does not already show, so the exposure is the inference cost, bounded by the
# endpoint's own max_concurrency of 5.
#
# No cors block here: CORSMiddleware in app.py already sets these headers, and
# a Function URL cors block sets them too. Both firing means duplicate
# Access-Control-Allow-Origin headers, which browsers reject outright. Keeping
# it in the app means the container behaves the same under plain uvicorn.
resource "aws_lambda_function_url" "predict" {
  count = var.enable_deploy ? 1 : 0

  function_name      = aws_lambda_function.predict[0].function_name
  authorization_type = "NONE"
}
