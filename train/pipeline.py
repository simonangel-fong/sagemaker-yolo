# pipeline.py
# Defines the training pipeline: preprocess -> train -> evaluate -> register.
#
# Hyperparameters come from hyperparams.json, written by the sweep notebook.
# Nothing here talks to MLflow, so the tracking server can stay shut down.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sagemaker.core.helper.session_helper import Session
from sagemaker.core.workflow.pipeline_context import PipelineSession
from sagemaker.core import image_uris
from sagemaker.core.processing import ScriptProcessor
from sagemaker.core.shapes import (
    ProcessingInput,
    ProcessingOutput,
    ProcessingS3Input,
    ProcessingS3Output,
)

from sagemaker.train import ModelTrainer
from sagemaker.train.configs import (
    InputData,
    Compute,
    SourceCode,
    OutputDataConfig,
)

from sagemaker.mlops.workflow.pipeline import Pipeline
from sagemaker.mlops.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.serve.model_builder import ModelBuilder
from sagemaker.mlops.workflow.model_step import ModelStep
from sagemaker.mlops.workflow.condition_step import ConditionStep
from sagemaker.core.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.core.workflow.parameters import ParameterFloat, ParameterInteger
from sagemaker.core.workflow.properties import PropertyFile
from sagemaker.core.workflow.functions import JsonGet

try:  # `python train/pipeline.py` and `python -m train.pipeline` both work
    from train import config
except ImportError:
    import config

PIPELINE_NAME = "sakemaker-yolo-pipeline"

# Overridable per execution. Everything else in hyperparams.json is passed to
# the training job as-is.
TUNABLE = ("epochs", "imgsz", "batch")


def build_pipeline(
    role: str,
    bucket: str,
    train_image: str,
    hyperparameters: dict,
    provenance: dict | None = None,
    session: PipelineSession | None = None,
    region: str | None = None,
) -> Pipeline:
    """
    Build the pipeline definition.

    `hyperparameters` must carry at least epochs/imgsz/batch; extra keys from a
    wider sweep are forwarded to train.py untouched. epochs/imgsz/batch become
    pipeline parameters so a single execution can override them without
    redefining the pipeline; the rest are baked into the definition.
    """
    pipeline_session = session or PipelineSession()
    region = region or Session().boto_region_name
    provenance = provenance or {}

    input_s3_uri = f"s3://{bucket}/{config.RAW_PREFIX}/"

    # ##############################
    # Pipeline parameters
    # ##############################
    param_epochs = ParameterInteger("Epochs", hyperparameters["epochs"])
    param_imgsz = ParameterInteger("ImageSize", hyperparameters["imgsz"])
    param_batch = ParameterInteger("Batch", hyperparameters["batch"])
    param_min_map = ParameterFloat("MinMap", config.MIN_MAP)

    # #########################################################
    # Shared images
    # #########################################################
    sklearn_image = image_uris.retrieve(
        framework="sklearn",
        region=region,
        version="1.2-1",
        py_version="py3",
        instance_type=config.PROCESS_INSTANCE_TYPE,
    )

    inference_image = image_uris.retrieve(
        framework="pytorch",
        region=region,
        version="2.6",
        py_version="py312",
        instance_type=config.PROCESS_INSTANCE_TYPE,
        image_scope="inference",
    )

    # #########################################################
    # 1. ProcessingStep
    # #########################################################
    processor = ScriptProcessor(
        image_uri=sklearn_image,
        command=["python3"],
        role=role,
        instance_type=config.PROCESS_INSTANCE_TYPE,
        instance_count=1,
        sagemaker_session=pipeline_session,
    )

    process_args = processor.run(
        code="steps/preprocess.py",
        inputs=[
            ProcessingInput(
                input_name="yolo",
                s3_input=ProcessingS3Input(
                    s3_uri=input_s3_uri,
                    local_path="/opt/ml/processing/input",
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            )
        ],
        outputs=[
            ProcessingOutput(
                output_name="split",
                s3_output=ProcessingS3Output(
                    s3_uri=f"s3://{bucket}/{config.PREFIX}/split",
                    local_path="/opt/ml/processing/split",
                    s3_upload_mode="EndOfJob",
                ),
            ),
            ProcessingOutput(
                output_name="config",
                s3_output=ProcessingS3Output(
                    s3_uri=f"s3://{bucket}/{config.PREFIX}/config",
                    local_path="/opt/ml/processing/config",
                    s3_upload_mode="EndOfJob",
                ),
            ),
        ],
    )

    step_process = ProcessingStep(
        name="ProcessYolo",
        step_args=process_args,
    )

    split_uri = (
        step_process.properties.ProcessingOutputConfig.Outputs["split"].S3Output.S3Uri
    )
    config_uri = (
        step_process.properties.ProcessingOutputConfig.Outputs["config"].S3Output.S3Uri
    )

    # #########################################################
    # 2. TrainingStep
    # #########################################################
    # tunables as parameters, everything else from the file
    train_hyperparameters = {
        key: value for key, value in hyperparameters.items() if key not in TUNABLE
    }
    train_hyperparameters.update(
        {
            "epochs": param_epochs,
            "imgsz": param_imgsz,
            "batch": param_batch,
        }
    )

    # recorded on the model so the artifact outlives the tracking server
    if provenance:
        train_hyperparameters["provenance"] = json.dumps(
            provenance, separators=(",", ":")
        )

    trainer = ModelTrainer(
        training_image=train_image,
        role=role,
        compute=Compute(
            instance_type=config.TRAIN_INSTANCE_TYPE,
            instance_count=1,
        ),
        sagemaker_session=pipeline_session,
        # without this the model lands in the account default bucket
        output_data_config=OutputDataConfig(
            s3_output_path=f"s3://{bucket}/{config.PREFIX}/model",
        ),
        # ultralytics and the pretrained weights are baked into the image,
        # so only the entry script is uploaded
        source_code=SourceCode(
            source_dir="steps",
            entry_script="train.py",
        ),
        hyperparameters=train_hyperparameters,
        input_data_config=[
            # mounted at /opt/ml/input/data/split -- where data.yaml points
            InputData(channel_name="split", data_source=split_uri),
            # mounted at /opt/ml/input/data/config -- holds data.yaml
            InputData(channel_name="config", data_source=config_uri),
        ],
    )

    step_train = TrainingStep(
        name="TrainYolo",
        step_args=trainer.train(),
    )

    model_artifacts = step_train.properties.ModelArtifacts.S3ModelArtifacts

    # #########################################################
    # 3. EvaluationStep
    # #########################################################
    eval_processor = ScriptProcessor(
        image_uri=train_image,
        command=["python3"],
        role=role,
        instance_type=config.PROCESS_INSTANCE_TYPE,
        instance_count=1,
        sagemaker_session=pipeline_session,
    )

    eval_args = eval_processor.run(
        code="steps/evaluate.py",
        # evaluate at the size the model was trained at
        arguments=["--imgsz", param_imgsz.to_string()],
        inputs=[
            ProcessingInput(
                input_name="model",
                s3_input=ProcessingS3Input(
                    s3_uri=model_artifacts,
                    local_path="/opt/ml/processing/model",
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
            ProcessingInput(
                input_name="split",
                s3_input=ProcessingS3Input(
                    s3_uri=split_uri,
                    local_path="/opt/ml/processing/split",
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
            ProcessingInput(
                input_name="config",
                s3_input=ProcessingS3Input(
                    s3_uri=config_uri,
                    local_path="/opt/ml/processing/config",
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="evaluation",
                s3_output=ProcessingS3Output(
                    s3_uri=f"s3://{bucket}/{config.PREFIX}/evaluation",
                    local_path="/opt/ml/processing/evaluation",
                    s3_upload_mode="EndOfJob",
                ),
            )
        ],
    )

    # lets the condition below read a value out of evaluation.json
    evaluation_report = PropertyFile(
        name="EvaluationReport",
        output_name="evaluation",
        path="evaluation.json",
    )

    step_evaluate = ProcessingStep(
        name="EvaluateYolo",
        step_args=eval_args,
        property_files=[evaluation_report],
    )

    # ---------------------------------------------------------
    # 4. Register model
    # ---------------------------------------------------------
    model_builder = ModelBuilder(
        s3_model_data_url=model_artifacts,
        image_uri=inference_image,
        role_arn=role,
        sagemaker_session=pipeline_session,
    )

    register_args = model_builder.register(
        model_package_group_name=config.MODEL_PACKAGE_GROUP,
        content_types=["application/x-image"],
        response_types=["application/json"],
        # serverless endpoints have no instance type; these describe what the
        # package supports, and the deploy pipeline picks the real one
        inference_instances=[config.PROCESS_INSTANCE_TYPE],
        approval_status="PendingManualApproval",
    )

    step_register = ModelStep(
        name="RegisterYolo",
        step_args=register_args,
    )

    # ---------------------------------------------------------
    # 5. ConditionStep: register only when the model is good enough
    # ---------------------------------------------------------
    step_condition = ConditionStep(
        name="CheckMap",
        conditions=[
            ConditionGreaterThanOrEqualTo(
                left=JsonGet(
                    step_name=step_evaluate.name,
                    property_file=evaluation_report,
                    json_path=config.METRIC,
                ),
                right=param_min_map,
            )
        ],
        # below the threshold nothing runs, and the execution still succeeds
        if_steps=[step_register],
        else_steps=[],
    )

    return Pipeline(
        name=PIPELINE_NAME,
        sagemaker_session=pipeline_session,
        parameters=[param_epochs, param_imgsz, param_batch, param_min_map],
        steps=[
            step_process,
            step_train,
            step_evaluate,
            # step_register runs inside this condition
            step_condition,
        ],
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-arn", required=True)  # sagemaker iam role
    parser.add_argument("--bucket", required=True)  # project bucket
    parser.add_argument("--train-image", required=True)  # ecr training image

    parser.add_argument(
        "--hyperparams",
        type=Path,
        default=config.HYPERPARAMS_PATH,
        help="hyperparameter contract written by the sweep notebook",
    )

    # explicit overrides win over the file, for a smoke run
    for name in TUNABLE:
        parser.add_argument(f"--{name}", type=int, default=None)

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the definition without creating or starting anything",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="start the execution and exit, for CI",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        hyperparameters, provenance = config.load_hyperparams(args.hyperparams)
    except config.HyperparamsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    overrides = {name: getattr(args, name) for name in TUNABLE}
    overrides = {k: v for k, v in overrides.items() if v is not None}
    if overrides:
        hyperparameters = {**hyperparameters, **overrides}
        # the file no longer describes this run
        provenance = {**provenance, "overridden": sorted(overrides)}
        print(f"override   {overrides}")

    print(f"hyperparams {config.describe(hyperparameters, provenance)}")

    pipeline = build_pipeline(
        role=args.role_arn,
        bucket=args.bucket,
        train_image=args.train_image,
        hyperparameters=hyperparameters,
        provenance=provenance,
    )

    if args.dry_run:
        print(pipeline.definition())
        return 0

    pipeline.upsert(role_arn=args.role_arn)
    execution = pipeline.start()
    print(f"execution  {execution.arn}")

    if args.no_wait:
        return 0

    execution.wait()
    print("Pipeline finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
