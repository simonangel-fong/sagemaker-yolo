# sagemaker-iam.tf

# ##############################
# IAM: Sagemaker
# ##############################
resource "aws_iam_role" "sagemaker_execution" {
  name = "${local.prefix_name}-sagemaker-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_full_access" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

resource "aws_iam_role_policy_attachment" "bucket_full" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# ##############################
# IAM policy: MLflow access
# ##############################
data "aws_iam_policy_document" "mlflow_access" {

  # allow mlflow instance for mlflow actions
  statement {
    sid    = "MlflowTracking"
    effect = "Allow"

    actions = ["sagemaker-mlflow:*"]

    resources = [aws_sagemaker_mlflow_tracking_server.yolo.arn]
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
  name        = "${local.prefix_name}-mlflow-access"
  description = "Studio execution role access to the MLflow tracking server."
  policy      = data.aws_iam_policy_document.mlflow_access.json
}

resource "aws_iam_role_policy_attachment" "mlflow_access" {
  role       = aws_iam_role.sagemaker_execution.name
  policy_arn = aws_iam_policy.mlflow_access.arn
}
