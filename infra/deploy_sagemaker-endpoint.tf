# sagemaker-endpoint.tf

# ##############################
# Model
# ##############################
# Deployed from the model registry
resource "aws_sagemaker_model" "yolo" {
  count = var.enable_deploy ? 1 : 0

  name               = "${local.prefix_name}-${var.model_version}"
  execution_role_arn = aws_iam_role.sagemaker_execution.arn

  # the PyTorch inference DLC
  container {
    model_package_name = "arn:aws:sagemaker:${var.aws_region}:${data.aws_caller_identity.current.account_id}:model-package/${local.project_name}/${var.model_version}"

    environment = {
      SAGEMAKER_PROGRAM             = "inference.py"
      SAGEMAKER_SUBMIT_DIRECTORY    = "/opt/ml/model/code"
      SAGEMAKER_CONTAINER_LOG_LEVEL = "20"

      CONF_THRESHOLD = local.endpoint_conf_threshold
    }
  }

  tags = local.default_tags
}

# ##############################
# Endpoint configuration
# ##############################
# Serverless endpoint
resource "aws_sagemaker_endpoint_configuration" "yolo" {
  count = var.enable_deploy ? 1 : 0

  name = "${local.prefix_name}-${var.model_version}"

  production_variants {
    variant_name = "AllTraffic"
    model_name   = aws_sagemaker_model.yolo[0].name

    serverless_config {
      memory_size_in_mb = local.endpoint_memory_mb
      max_concurrency   = local.endpoint_max_concurrency
    }
  }

  tags = local.default_tags
}

# ##############################
# Endpoint
# ##############################
resource "aws_sagemaker_endpoint" "yolo" {
  count = var.enable_deploy ? 1 : 0

  name                 = local.prefix_name
  endpoint_config_name = aws_sagemaker_endpoint_configuration.yolo[0].name

  tags = local.default_tags
}
