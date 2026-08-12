"""
Create or update the pipeline, and optionally start an execution.

    python pipeline/run.py --dry-run     # print the definition, touch nothing
    python pipeline/run.py               # upsert
    python pipeline/run.py --execute     # upsert and run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import boto3
from sagemaker.core.workflow.pipeline_context import PipelineSession

# so the script runs from anywhere, not just from inside pipeline/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from definition import build_pipeline


def resolve_role() -> str:
    """Studio provides the execution role; outside it, pass --role."""
    if "SAGEMAKER_ROLE_ARN" in os.environ:
        return os.environ["SAGEMAKER_ROLE_ARN"]

    from sagemaker.core.helper.session_helper import get_execution_role

    try:
        return get_execution_role()
    except Exception as exc:
        # off Studio (CI, a plain VM) there is no notebook role to look up, and
        # the SDK's own error does not say what to do about it
        raise RuntimeError(
            "could not resolve an execution role: this only works inside "
            "SageMaker Studio. Pass --role, or set SAGEMAKER_ROLE_ARN to the "
            "ARN of a role the pipeline can assume."
        ) from exc


def resolve_bucket() -> str:
    """Same env file the notebooks read, so both agree on the bucket."""
    if "BUCKET" in os.environ:
        return os.environ["BUCKET"]

    env_file = Path.home() / ".sagemaker-yolo.env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            key, _, val = line.partition("=")
            if key.strip() == "BUCKET":
                return val.strip()

    raise RuntimeError("set BUCKET or pass --bucket")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role")
    parser.add_argument("--bucket")
    parser.add_argument("--region")
    parser.add_argument("--name", default="sagemaker-yolo-train")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    # an empty AWS_REGION (an unset CI variable) reaches boto3 as "", which it
    # accepts and then fails on much later with "Invalid endpoint"
    region = (args.region or boto3.Session().region_name or "").strip()
    if not region:
        # bare runners have no ~/.aws/config, so boto3 reports no region at all
        raise RuntimeError(
            "no AWS region configured: pass --region, or set AWS_REGION "
            "(AWS_DEFAULT_REGION also works)."
        )

    bucket = args.bucket or resolve_bucket()
    role = args.role or resolve_role()

    pipeline = build_pipeline(
        role=role,
        bucket=bucket,
        region=region,
        name=args.name,
        session=PipelineSession(default_bucket=bucket),
    )

    if args.dry_run:
        print(json.dumps(json.loads(pipeline.definition()), indent=2))
        return

    pipeline.upsert(role_arn=role)
    print(f"upserted {pipeline.name}")

    if args.execute:
        execution = pipeline.start(parameters={"Limit": args.limit})
        print(f"started  {execution.arn}")


if __name__ == "__main__":
    main()
