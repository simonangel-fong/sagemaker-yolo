# # sagemaker-endpoint.tf

# # ##############################
# # Model
# # ##############################
# # The PyTorch inference DLC, not a custom image: it ships the SageMaker Python
# # inference toolkit, which is what discovers code/inference.py inside the
# # tarball and calls model_fn / input_fn / predict_fn. The handler itself only
# # needs onnxruntime, pulled in from code/requirements.txt at container start.
# resource "aws_sagemaker_model" "yolo" {
#   count = var.enable_deploy ? 1 : 0

#   name               = "${local.prefix_name}-${var.model_run}"
#   execution_role_arn = aws_iam_role.sagemaker_execution.arn

#   primary_container {
#     image          = var.inference_image_uri
#     model_data_url = "s3://${aws_s3_bucket.yolo.id}/deploy/${var.model_run}/model.tar.gz"

#     environment = {
#       # tells the toolkit which file in code/ holds the handler
#       SAGEMAKER_PROGRAM             = "inference.py"
#       SAGEMAKER_SUBMIT_DIRECTORY    = "/opt/ml/model/code"
#       SAGEMAKER_CONTAINER_LOG_LEVEL = "20"

#       # detection thresholds, read by inference.py; changing these does not
#       # require repackaging the model
#       CONF_THRESHOLD = var.conf_threshold
#       IOU_THRESHOLD  = var.iou_threshold
#     }
#   }

#   tags = local.default_tags
# }

# # ##############################
# # Endpoint configuration
# # ##############################
# # Serverless: this endpoint sees sporadic traffic, so provisioned instances
# # would bill 24/7 for a model that is idle most of the day.
# resource "aws_sagemaker_endpoint_configuration" "yolo" {
#   count = var.enable_deploy ? 1 : 0

#   name = "${local.prefix_name}-${var.model_run}"

#   production_variants {
#     variant_name = "AllTraffic"
#     model_name   = aws_sagemaker_model.yolo[0].name

#     serverless_config {
#       memory_size_in_mb = var.serverless_memory_mb
#       max_concurrency   = var.serverless_max_concurrency
#     }
#   }

#   tags = local.default_tags
# }

# # ##############################
# # Endpoint
# # ##############################
# resource "aws_sagemaker_endpoint" "yolo" {
#   count = var.enable_deploy ? 1 : 0

#   name                 = "${local.prefix_name}-yolo"
#   endpoint_config_name = aws_sagemaker_endpoint_configuration.yolo[0].name

#   tags = local.default_tags
# }
