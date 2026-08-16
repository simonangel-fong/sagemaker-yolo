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

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"

      values = [
        "repo:${local.repo_owner}@${var.repo_owner_id}/${local.repo_name}@${var.repo_id}:*",
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
