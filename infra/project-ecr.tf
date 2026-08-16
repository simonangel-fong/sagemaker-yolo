# ecr.tf

# ##############################
# ECR: training image
# ##############################
resource "aws_ecr_repository" "train" {
  name = "${local.project_name}-train"

  # let terraform destroy the repo even when images are still in it
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.yolo.arn
  }
}

# keep the last 5 images; every build pushes a new one
resource "aws_ecr_lifecycle_policy" "train" {
  repository = aws_ecr_repository.train.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ##############################
# ECR: lambda image
# ##############################
resource "aws_ecr_repository" "lambda" {
  name = "${local.project_name}-lambda"

  # let terraform destroy the repo even when images are still in it
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.yolo.arn
  }
}

resource "aws_ecr_lifecycle_policy" "lambda" {
  repository = aws_ecr_repository.lambda.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
