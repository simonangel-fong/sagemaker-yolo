# cicd_terraform.tf

# ##############################
# IAM: role assumed by GitHub Actions for terraform
# ##############################
data "aws_iam_policy_document" "github_terraform_assume" {
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

    # Scoped to the `dev` environment
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"

      values = [
        "${local.oidc_sub_prefix}:environment:${local.oidc_environment}",
      ]
    }
  }
}

resource "aws_iam_role" "github_terraform" {
  name               = "${local.prefix_name}-github-terraform-role"
  assume_role_policy = data.aws_iam_policy_document.github_terraform_assume.json

  tags = local.default_tags
}

resource "aws_iam_role_policy_attachment" "github_terraform_admin" {
  role       = aws_iam_role.github_terraform.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# Redundant while AdministratorAccess is attached above, and kept deliberately:
# it records the minimum this role needs on the backend, so dropping admin for a
# least-privilege policy does not have to rediscover it. `s3:DeleteObject` is
# required to clear the lock object under `use_lockfile=true`.
data "aws_iam_policy_document" "github_terraform_state" {
  statement {
    sid     = "AllowStateBucketList"
    effect  = "Allow"
    actions = ["s3:ListBucket"]

    resources = ["arn:aws:s3:::${var.tf_state_bucket}"]
  }

  statement {
    sid    = "AllowStateObjectAccess"
    effect = "Allow"

    actions = [
      "s3:DeleteObject",
      "s3:GetObject",
      "s3:PutObject",
    ]

    resources = ["arn:aws:s3:::${var.tf_state_bucket}/*"]
  }
}

resource "aws_iam_role_policy" "github_terraform_state" {
  name   = "${local.prefix_name}-github-terraform-state"
  role   = aws_iam_role.github_terraform.id
  policy = data.aws_iam_policy_document.github_terraform_state.json
}

output "github_terraform_role_arn" {
  value = aws_iam_role.github_terraform.arn
}
