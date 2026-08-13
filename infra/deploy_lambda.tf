# # lambda.tf

# # ##############################
# # Package
# # ##############################
# # app.py has no dependencies outside the runtime -- boto3 ships with Lambda --
# # so the zip is the single file and no build step is needed.
# data "archive_file" "predict" {
#   count = var.enable_deploy ? 1 : 0

#   type        = "zip"
#   source_file = "${path.module}/../deploy/lambda/app.py"
#   output_path = "${path.module}/build/predict.zip"
# }

# # ##############################
# # IAM
# # ##############################
# resource "aws_iam_role" "lambda_predict" {
#   count = var.enable_deploy ? 1 : 0

#   name = "${local.prefix_name}-lambda-predict-role"

#   assume_role_policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Effect    = "Allow"
#         Principal = { Service = "lambda.amazonaws.com" }
#         Action    = "sts:AssumeRole"
#       }
#     ]
#   })
# }

# resource "aws_iam_role_policy_attachment" "lambda_logs" {
#   count = var.enable_deploy ? 1 : 0

#   role       = aws_iam_role.lambda_predict[0].name
#   policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
# }

# # Scoped to the one endpoint: this function has no reason to reach any other
# # SageMaker resource, and SageMakerFullAccess on an internet-facing function
# # would be a much larger blast radius than the job needs.
# data "aws_iam_policy_document" "lambda_invoke_endpoint" {
#   count = var.enable_deploy ? 1 : 0

#   statement {
#     sid       = "InvokeYoloEndpoint"
#     effect    = "Allow"
#     actions   = ["sagemaker:InvokeEndpoint"]
#     resources = [aws_sagemaker_endpoint.yolo[0].arn]
#   }
# }

# resource "aws_iam_policy" "lambda_invoke_endpoint" {
#   count = var.enable_deploy ? 1 : 0

#   name        = "${local.prefix_name}-lambda-invoke-endpoint"
#   description = "Invoke the YOLO inference endpoint."
#   policy      = data.aws_iam_policy_document.lambda_invoke_endpoint[0].json
# }

# resource "aws_iam_role_policy_attachment" "lambda_invoke_endpoint" {
#   count = var.enable_deploy ? 1 : 0

#   role       = aws_iam_role.lambda_predict[0].name
#   policy_arn = aws_iam_policy.lambda_invoke_endpoint[0].arn
# }

# # ##############################
# # Function
# # ##############################
# resource "aws_lambda_function" "predict" {
#   count = var.enable_deploy ? 1 : 0

#   function_name = "${local.prefix_name}-predict"
#   role          = aws_iam_role.lambda_predict[0].arn

#   filename         = data.archive_file.predict[0].output_path
#   source_code_hash = data.archive_file.predict[0].output_base64sha256

#   handler = "app.handler"
#   runtime = "python3.12"

#   # the endpoint itself can take ~5s on a cold start, so the default 3s would
#   # time out the first request of the day rather than the model failing
#   timeout     = 30
#   memory_size = 512

#   environment {
#     variables = {
#       ENDPOINT_NAME = aws_sagemaker_endpoint.yolo[0].name
#       MODEL_NAME    = var.web_model_name
#       IMGSZ         = "640"
#       CLASSES       = jsonencode(["car_plate"])
#       ALLOW_ORIGIN  = var.allow_origin
#     }
#   }

#   tags = local.default_tags
# }

# resource "aws_cloudwatch_log_group" "predict" {
#   count = var.enable_deploy ? 1 : 0

#   name              = "/aws/lambda/${aws_lambda_function.predict[0].function_name}"
#   retention_in_days = 14
#   tags              = local.default_tags
# }

# # ##############################
# # Function URL
# # ##############################
# # NONE auth: CloudFront fronts this and the browser cannot sign SigV4. The
# # function is a thin wrapper over one endpoint and returns no data the page
# # does not already show, so the exposure is the inference cost, bounded by the
# # endpoint's own max_concurrency of 5.
# resource "aws_lambda_function_url" "predict" {
#   count = var.enable_deploy ? 1 : 0

#   function_name      = aws_lambda_function.predict[0].function_name
#   authorization_type = "NONE"

#   cors {
#     allow_origins = [var.allow_origin]
#     allow_methods = ["GET", "POST"]
#     allow_headers = ["content-type"]
#     max_age       = 3600
#   }
# }
