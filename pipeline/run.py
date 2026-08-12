"""
Create/update the pipeline and optionally start a run.

    python -m pipeline.run --dry-run     # print the JSON definition only
    python -m pipeline.run               # upsert into SageMaker
    python -m pipeline.run --start       # upsert, then execute

src/ is uploaded first because the processing step mounts it as an input
channel -- the definition points at that prefix, so it must exist before a
run starts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipeline import config
from pipeline.definition import build_pipeline
from src import s3_sync

REPO = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="print the definition without calling AWS")
    parser.add_argument("--start", action="store_true",
                        help="start an execution after upserting")
    parser.add_argument("--wait", action="store_true",
                        help="block until the execution finishes")
    parser.add_argument("--param", action="append", default=[],
                        metavar="NAME=VALUE",
                        help="override a pipeline parameter; repeatable")
    args = parser.parse_args()

    pipeline = build_pipeline()

    if args.dry_run:
        print(json.dumps(json.loads(pipeline.definition()), indent=2))
        return

    stats = s3_sync.upload(REPO / "src", config.s3("code", "src"), delete=True)
    print(f"src upload   {stats}")

    pipeline.upsert(role_arn=config.ROLE_ARN)
    print(f"upserted     {config.PIPELINE_NAME}")

    if not args.start:
        return

    overrides = dict(p.split("=", 1) for p in args.param)
    if overrides:
        print(f"parameters   {overrides}")

    execution = pipeline.start(parameters=overrides or None)
    print(f"started      {execution.arn}")

    if args.wait:
        execution.wait()
        for step in execution.list_steps():
            print(f"  {step['StepName']:16} {step['StepStatus']}")


if __name__ == "__main__":
    main()
