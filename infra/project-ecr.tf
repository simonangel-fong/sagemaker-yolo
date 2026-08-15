# ecr.tf

# ##############################
# ECR: training image
# ##############################
resource "aws_ecr_repository" "train" {
  name = "${var.project}-train"

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
# ECR: predict image
# ##############################
# The predict function outgrew a zip: FastAPI and its dependencies push the
# package past Lambda's 250 MB unzipped limit, so it ships as a container.
resource "aws_ecr_repository" "predict" {
  name = "${var.project}-predict"

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

resource "aws_ecr_lifecycle_policy" "predict" {
  repository = aws_ecr_repository.predict.name

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
