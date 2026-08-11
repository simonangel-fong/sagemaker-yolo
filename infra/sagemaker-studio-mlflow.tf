# sagemaker-studio-mlflow.tf

locals {
  mlflow_prefix = "mlflow"
}


# ##############################
# MLflow app role
# ##############################
resource "aws_iam_role" "mlflow" {
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
  name        = "${local.prefix_name}-mlflow-artifacts"
  description = "MLflow app access to the artifact store."
  policy      = data.aws_iam_policy_document.mlflow_artifacts.json
}

resource "aws_iam_role_policy_attachment" "mlflow_artifacts" {
  role       = aws_iam_role.mlflow.name
  policy_arn = aws_iam_policy.mlflow_artifacts.arn
}

# ##############################
# MLflow app
# ##############################
resource "aws_sagemaker_mlflow_app" "yolo" {
  name                   = local.prefix_name
  default_domain_id_list = [aws_sagemaker_domain.yolo.id]
  role_arn               = aws_iam_role.mlflow.arn

  artifact_store_uri = "s3://${aws_s3_bucket.yolo.id}/${local.mlflow_prefix}/"
}
