"""
Shared pipeline settings.

Values come from `terraform -chdir=infra output`, resolved once here so the
step modules do not each hardcode an account-specific ARN. Environment
variables win, which keeps the same definition usable against a second stack.
"""

from __future__ import annotations

import os

REGION = os.environ.get("AWS_REGION", "ca-central-1")

# infra output: studio_domain_role_arn
ROLE_ARN = os.environ.get(
    "SAGEMAKER_ROLE_ARN",
    "arn:aws:iam::099139718958:role/sagemaker-yolo-dev-sagemaker-execution-role",
)

# infra output: s3_bucket_name
BUCKET = os.environ.get("SAGEMAKER_BUCKET", "sagemaker-yolo-dev-0luf20")

PREFIX = os.environ.get("SAGEMAKER_PREFIX", "pipeline")

PIPELINE_NAME = "sagemaker-yolo"

# raw image/label pairs, uploaded by the s3_sync_command in infra outputs
RAW_URI = f"s3://{BUCKET}/data/raw"


def s3(*parts: str) -> str:
    """Build a pipeline-scoped S3 URI."""
    return "/".join((f"s3://{BUCKET}/{PREFIX}", *parts))
