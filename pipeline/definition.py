"""
Training pipeline definition.

Step 1 (preprocess) only; the remaining steps land in later phases.
"""

from __future__ import annotations

from pathlib import Path

from sagemaker.core import image_uris
from sagemaker.core.processing import ScriptProcessor
from sagemaker.core.shapes import (
    ProcessingInput,
    ProcessingOutput,
    ProcessingS3Input,
    ProcessingS3Output,
)
from sagemaker.core.workflow.parameters import (
    ParameterFloat,
    ParameterInteger,
    ParameterString,
)
from sagemaker.core.workflow.pipeline_context import PipelineSession
from sagemaker.mlops.workflow.pipeline import Pipeline
from sagemaker.mlops.workflow.steps import CacheConfig, ProcessingStep

ROOT = Path(__file__).resolve().parent.parent


def _sdk_path(path: Path) -> str:
    """
    The SDK urlparse()s local paths, so a Windows drive letter ("C:\\...") is
    read as a URL scheme and rejected. Relative paths have no scheme, so prefer
    one when the cwd allows it.
    """
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return str(path)


# sklearn image is the smallest maintained one with a usable python; the step
# only needs the stdlib plus src/, so no custom container is warranted yet
SKLEARN_VERSION = "1.2-1"


def build_pipeline(
    role: str,
    bucket: str,
    region: str,
    name: str = "sagemaker-yolo-train",
    session: PipelineSession | None = None,
) -> Pipeline:
    """Assemble the pipeline. Parameters stay overridable at execution time."""
    session = session or PipelineSession(default_bucket=bucket)

    default_instance_type = "ml.m5.large"

    raw_uri = ParameterString("RawDataUri", f"s3://{bucket}/data/raw")
    instance_type = ParameterString("PreprocessInstanceType", default_instance_type)
    val_fraction = ParameterFloat("ValFraction", 0.2)
    seed = ParameterInteger("SplitSeed", 0)
    # 0 means every pair; ParameterInteger cannot express None
    limit = ParameterInteger("Limit", 0)

    processor = ScriptProcessor(
        # retrieve() knows the per-region (and per-partition) ECR account, which
        # a hardcoded URI gets wrong outside the usual commercial regions. It
        # needs a concrete instance type, so the parameter's default is used to
        # pick the image; overriding the parameter at execution time still works
        # because cpu/gpu selection only matters for framework images.
        image_uri=image_uris.retrieve(
            framework="sklearn",
            region=region,
            version=SKLEARN_VERSION,
            py_version="py3",
            instance_type=default_instance_type,
        ),
        command=["python3"],
        instance_type=instance_type,
        instance_count=1,
        base_job_name=f"{name}-preprocess",
        role=role,
        sagemaker_session=session,
    )

    step_args = processor.run(
        code=_sdk_path(ROOT / "pipeline" / "steps" / "preprocess.py"),
        inputs=[
            ProcessingInput(
                input_name="raw",
                s3_input=ProcessingS3Input(
                    s3_uri=raw_uri,
                    s3_data_type="S3Prefix",
                    local_path="/opt/ml/processing/input",
                ),
            ),
            # src/ ships alongside the script so the step reuses data_loader
            ProcessingInput(
                # not "code": the SDK adds its own "code" input for the script
                input_name="src",
                s3_input=ProcessingS3Input(
                    s3_uri=_sdk_path(ROOT / "src"),
                    s3_data_type="S3Prefix",
                    local_path="/opt/ml/processing/code/src",
                ),
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="split",
                s3_output=ProcessingS3Output(
                    s3_uri=f"s3://{bucket}/pipeline/split",
                    local_path="/opt/ml/processing/split",
                    s3_upload_mode="EndOfJob",
                ),
            ),
            ProcessingOutput(
                output_name="config",
                s3_output=ProcessingS3Output(
                    s3_uri=f"s3://{bucket}/pipeline/config",
                    local_path="/opt/ml/processing/config",
                    s3_upload_mode="EndOfJob",
                ),
            ),
        ],
        arguments=[
            "--val-fraction", val_fraction.to_string(),
            "--seed", seed.to_string(),
            "--limit", limit.to_string(),
        ],
    )

    preprocess = ProcessingStep(
        name="Preprocess",
        step_args=step_args,
        # re-running the split on unchanged inputs costs money and produces the
        # same output; the seed is a parameter, so a changed seed misses cache
        cache_config=CacheConfig(enable_caching=True, expire_after="P30D"),
    )

    return Pipeline(
        name=name,
        parameters=[raw_uri, instance_type, val_fraction, seed, limit],
        steps=[preprocess],
        sagemaker_session=session,
    )
