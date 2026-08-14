# sagemaker-endpoint.tf

# ##############################
# Model
# ##############################
# Deployed from the model registry, not a loose S3 path: the training pipeline
# registers a package whose InferenceSpecification already carries the image
# and the artifact, so the endpoint follows whatever that version points at.
#
# The package must be Approved first; SageMaker refuses to deploy one that is
# still PendingManualApproval.
resource "aws_sagemaker_model" "yolo" {
  count = var.enable_deploy ? 1 : 0

  name               = "${local.prefix_name}-${var.model_version}"
  execution_role_arn = aws_iam_role.sagemaker_execution.arn

  # the PyTorch inference DLC recorded on the package ships the SageMaker
  # inference toolkit, which discovers code/inference.py inside the tarball
  # and calls model_fn / input_fn / predict_fn
  container {
    model_package_name = "arn:aws:sagemaker:${var.aws_region}:${data.aws_caller_identity.current.account_id}:model-package/${var.model_package_group}/${var.model_version}"

    environment = {
      # tells the toolkit which file in code/ holds the handler
      SAGEMAKER_PROGRAM             = "inference.py"
      SAGEMAKER_SUBMIT_DIRECTORY    = "/opt/ml/model/code"
      SAGEMAKER_CONTAINER_LOG_LEVEL = "20"

      # read by inference.py; changing this does not require retraining
      CONF_THRESHOLD = var.conf_threshold
    }
  }

  tags = local.default_tags
}

# ##############################
# Endpoint configuration
# ##############################
# Serverless: this endpoint sees sporadic traffic, so provisioned instances
# would bill 24/7 for a model that is idle most of the day.
resource "aws_sagemaker_endpoint_configuration" "yolo" {
  count = var.enable_deploy ? 1 : 0

  name = "${local.prefix_name}-${var.model_version}"

  production_variants {
    variant_name = "AllTraffic"
    model_name   = aws_sagemaker_model.yolo[0].name

    serverless_config {
      memory_size_in_mb = var.serverless_memory_mb
      max_concurrency   = var.serverless_max_concurrency
    }
  }

  tags = local.default_tags
}

# ##############################
# Endpoint
# ##############################
resource "aws_sagemaker_endpoint" "yolo" {
  count = var.enable_deploy ? 1 : 0

  name                 = "${local.prefix_name}-yolo"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.yolo[0].name

  tags = local.default_tags
}
