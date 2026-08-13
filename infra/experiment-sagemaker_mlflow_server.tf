# sagemaker_mlflow_server.tf

locals {
  mlflow_prefix = "mlflow"
}

# ##############################
# IAM policy: MLflow access
# ##############################
data "aws_iam_policy_document" "mlflow_access" {
  count = var.enable_experiment ? 1 : 0

  # allow mlflow instance for mlflow actions
  statement {
    sid    = "MlflowTracking"
    effect = "Allow"

    actions = ["sagemaker-mlflow:*"]

    resources = [aws_sagemaker_mlflow_tracking_server.yolo[0].arn]
  }

  # allow mlflow server access in sagemaker
  statement {
    sid    = "MlflowServerAccess"
    effect = "Allow"

    actions = [
      "sagemaker:CreatePresignedMlflowTrackingServerUrl",
      "sagemaker:DescribeMlflowTrackingServer",
      "sagemaker:ListMlflowTrackingServers",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_policy" "mlflow_access" {
  count = var.enable_experiment ? 1 : 0

  name        = "${local.prefix_name}-mlflow-access"
  description = "Studio execution role access to the MLflow tracking server."
  policy      = data.aws_iam_policy_document.mlflow_access[0].json
}

resource "aws_iam_role_policy_attachment" "mlflow_access" {
  count = var.enable_experiment ? 1 : 0

  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = aws_iam_policy.mlflow_access[0].arn
}


# ##############################
# IAM rolw: MLflow tracking server role
# ##############################
resource "aws_iam_role" "mlflow" {
  count = var.enable_experiment ? 1 : 0

  name = "${local.prefix_name}-role-mlflow"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = ""
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
      },
    ]
  })
}

data "aws_iam_policy_document" "mlflow_artifacts" {

  # allow mlflow to access bucket.
  statement {
    sid    = "S3ListArtifactBucket"
    effect = "Allow"

    actions = [
      "s3:ListBucket",
      "s3:GetBucketLocation",
    ]

    resources = [aws_s3_bucket.yolo.arn]
  }

  statement {
    sid    = "S3ReadWriteArtifactPrefix"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
    ]

    resources = ["${aws_s3_bucket.yolo.arn}/${local.mlflow_prefix}/*"]
  }

  # allow mlflow for kms
  statement {
    sid    = "KmsUse"
    effect = "Allow"

    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]

    resources = [aws_kms_key.yolo.arn]
  }

  # allow mlflow for model
  statement {
    sid    = "ModelRegistry"
    effect = "Allow"

    actions = [
      "sagemaker:CreateModelPackageGroup",
      "sagemaker:CreateModelPackage",
      "sagemaker:DescribeModelPackage",
      "sagemaker:DescribeModelPackageGroup",
      "sagemaker:ListModelPackages",
      "sagemaker:UpdateModelPackage",
    ]

    resources = ["*"]
  }
}

resource "aws_iam_policy" "mlflow_artifacts" {
  count = var.enable_experiment ? 1 : 0

  name        = "${local.prefix_name}-mlflow-artifacts"
  description = "MLflow tracking server access to the artifact store."
  policy      = data.aws_iam_policy_document.mlflow_artifacts.json
}

resource "aws_iam_role_policy_attachment" "mlflow_artifacts" {
  count = var.enable_experiment ? 1 : 0

  role       = aws_iam_role.mlflow[0].name
  policy_arn = aws_iam_policy.mlflow_artifacts[0].arn
}

# ##############################
# MLflow tracking server
# ##############################
resource "aws_sagemaker_mlflow_tracking_server" "yolo" {
  count = var.enable_experiment ? 1 : 0

  tracking_server_name = local.prefix_name
  role_arn             = aws_iam_role.mlflow[0].arn

  artifact_store_uri = "s3://${aws_s3_bucket.yolo.id}/${local.mlflow_prefix}/"

  tracking_server_size = local.sagemaker_mlflow_server_size
  mlflow_version       = local.sagemaker_mlflow_version

  # enable mlflow register sagemaker model
  automatic_model_registration = true

  weekly_maintenance_window_start = "Sun:03:00"
}
