# cicd_oidc.tf
# GitHub Actions OIDC role

# ##############################
# OIDC provider
# ##############################
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

# ##############################
# IAM: role assumed by GitHub Actions
# ##############################
data "aws_iam_policy_document" "github_actions_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"

      values = [
        "repo:${local.github_owner}@${var.github_owner_id}/${local.github_repo}@${var.github_repo_id}:*",
      ]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${local.prefix_name}-github-actions-role"
  assume_role_policy = data.aws_iam_policy_document.github_actions_assume.json

  tags = local.default_tags
}

# ##############################
# IAM: ECR push permissions
# ##############################
data "aws_iam_policy_document" "github_actions_ecr" {
  # allow ecr auth
  statement {
    sid       = "AllowEcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Allow to Push to ecr
  statement {
    sid    = "AllowEcrPush"
    effect = "Allow"

    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]

    resources = [
      aws_ecr_repository.train.arn,
      aws_ecr_repository.inference.arn,
    ]
  }

  # Allow access to AWS Deep Learning Container
  statement {
    sid    = "AllowDlcBasePull"
    effect = "Allow"

    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]

    resources = ["arn:aws:ecr:${var.aws_region}:763104351884:repository/*"]
  }

  # Allow kms
  statement {
    sid    = "AllowKmsForEcr"
    effect = "Allow"

    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:Encrypt",
      "kms:GenerateDataKey*",
    ]

    resources = [aws_kms_key.yolo.arn]
  }

  # Allow access Lambda
  dynamic "statement" {
    for_each = var.enable_deploy ? [1] : []

    content {
      sid    = "AllowLambdaImageUpdate"
      effect = "Allow"

      actions = [
        "lambda:GetFunction",
        "lambda:UpdateFunctionCode",
      ]

      resources = [aws_lambda_function.inference[0].arn]
    }
  }
}

resource "aws_iam_role_policy" "github_actions_ecr" {
  name   = "${local.prefix_name}-github-actions-ecr"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_ecr.json
}
