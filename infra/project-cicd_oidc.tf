# cicd_oidc.tf
# GitHub Actions assumes this role via OIDC to build and push ECR images.
# No long-lived access keys are stored in the repository.

locals {
  # "owner/name" split into its two halves for the OIDC subject claim.
  github_owner     = split("/", var.github_repository)[0]
  github_repo_name = split("/", var.github_repository)[1]
}

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

    # Only workflows on this repository may assume the role.
    #
    # Repositories created on or after 2026-07-15 emit an immutable subject
    # claim that appends the permanent numeric owner and repository IDs after
    # each name: repo:owner@<owner-id>/name@<repo-id>:<context>. Binding to the
    # IDs is the point of the immutable claim -- deleting this repository and
    # recreating one with the same name yields new IDs, so a stale trust policy
    # cannot be used to mint tokens for the replacement.
    #
    # The subject is not narrowed to a branch: that would block
    # workflow_dispatch runs from any other ref.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"

      values = [
        "repo:${local.github_owner}@${var.github_owner_id}/${local.github_repo_name}@${var.github_repository_id}:*",
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
  # Auth token is account-wide and cannot be scoped to a repository.
  statement {
    sid       = "AllowEcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Push to the project's own repositories.
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
      aws_ecr_repository.predict.arn,
    ]
  }

  # The training image is built FROM an AWS Deep Learning Container held in
  # an ECR registry owned by AWS, so the pull is a cross-account read.
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

  # Both repositories are encrypted with the project key; without these the
  # push fails after the layers have already uploaded.
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

  # Roll the predict Lambda onto the image that was just pushed.
  dynamic "statement" {
    for_each = var.enable_deploy ? [1] : []

    content {
      sid    = "AllowLambdaImageUpdate"
      effect = "Allow"

      actions = [
        "lambda:GetFunction",
        "lambda:UpdateFunctionCode",
      ]

      resources = [aws_lambda_function.predict[0].arn]
    }
  }
}

resource "aws_iam_role_policy" "github_actions_ecr" {
  name   = "${local.prefix_name}-github-actions-ecr"
  role   = aws_iam_role.github_actions.id
  policy = data.aws_iam_policy_document.github_actions_ecr.json
}
