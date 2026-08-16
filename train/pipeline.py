# pipeline.py
# Defines the training pipeline: preprocess -> train -> evaluate -> register.
#
# Hyperparameters come from hyperparams.json, written by the sweep notebook.
# Nothing here talks to MLflow, so the tracking server can stay shut down.
"""
dry run and print the definition to validate:
    python pipeline.py --role-arn ... --bucket ... --train-image ... --dry-run

short smoke run:
    python pipeline.py --role-arn ... --bucket ... --train-image ... --epochs 3

start and exit
    python pipeline.py --role-arn ... --bucket ... --train-image ... --no-wait
"""


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
from sagemaker.core.workflow.parameters import ParameterFloat, ParameterString
from sagemaker.core.workflow.properties import PropertyFile
from sagemaker.core.workflow.functions import JsonGet, Join

# import config
try: 
    from train import config
except ImportError:
    import config

# pipeline name
PIPELINE_NAME = "sakemaker-yolo-pipeline"

# Overridable per execution.
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
    """
    pipeline_session = session or PipelineSession()
    region = region or Session().boto_region_name
    provenance = provenance or {}

    input_s3_uri = f"s3://{bucket}/{config.RAW_PREFIX}/"

    # the packaging step reads the handler from S3, so upload it at build time;
    # ScriptProcessor.run takes a single script and has no source_dir
    handler_s3_uri = pipeline_session.upload_data(
        path=str(config.INFERENCE_DIR),
        bucket=bucket,
        key_prefix=f"{config.PREFIX}/inference-code",
    )
    print(f"handler    {handler_s3_uri}")

    # ##############################
    # Pipeline parameters
    # ##############################
    param_epochs = ParameterString("Epochs", str(hyperparameters["epochs"]))
    param_imgsz = ParameterString("ImageSize", str(hyperparameters["imgsz"]))
    param_batch = ParameterString("Batch", str(hyperparameters["batch"]))
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
    # script processor to process data
    processor = ScriptProcessor(
        image_uri=sklearn_image,
        command=["python3"],
        role=role,
        instance_type=config.PROCESS_INSTANCE_TYPE,
        instance_count=1,
        sagemaker_session=pipeline_session,
    )

    # script processor script
    process_args = processor.run(
        # script to execute
        code="steps/preprocess.py",
        # data sources
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
        # output files
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

    # define a task to run script processor
    step_process = ProcessingStep(
        name="ProcessYolo",
        step_args=process_args,
    )

    # get split uri
    split_uri = (
        step_process.properties.ProcessingOutputConfig.Outputs["split"].S3Output.S3Uri
    )
    # get config uri
    config_uri = (
        step_process.properties.ProcessingOutputConfig.Outputs["config"].S3Output.S3Uri
    )

    # #########################################################
    # 2. TrainingStep
    # #########################################################
    # construct param
    train_hyperparameters = {
        key: value for key, value in hyperparameters.items() if key not in TUNABLE
    }

    # load param
    train_hyperparameters.update(
        {
            "epochs": param_epochs,
            "imgsz": param_imgsz,
            "batch": param_batch,
        }
    )

    # load provenance
    if provenance:
        train_hyperparameters["provenance"] = json.dumps(
            provenance, separators=(",", ":")
        )

    # construct trainer
    trainer = ModelTrainer(
        training_image=train_image,
        role=role,
        compute=Compute(
            instance_type=config.TRAIN_INSTANCE_TYPE,
            instance_count=1,
        ),
        sagemaker_session=pipeline_session,
        # custom output
        output_data_config=OutputDataConfig(
            s3_output_path=f"s3://{bucket}/{config.PREFIX}/model",
        ),
        # local entry point script 
        source_code=SourceCode(
            source_dir="steps",
            entry_script="train.py",
        ),
        hyperparameters=train_hyperparameters,
        input_data_config=[
            # mounted at /opt/ml/input/data/split
            InputData(channel_name="split", data_source=split_uri),
            # mounted at /opt/ml/input/data/config
            InputData(channel_name="config", data_source=config_uri),
        ],
    )

    # launch train job
    step_train = TrainingStep(
        name="TrainYolo",
        step_args=trainer.train(),
    )

    # get model artifact
    model_artifacts = step_train.properties.ModelArtifacts.S3ModelArtifacts

    # #########################################################
    # 3. PackageStep: inject the serving handler
    # #########################################################
    # the training job no longer writes code/ into the artifact, so the handler
    # is added here; only stdlib tarfile is needed, hence the cheap image
    packager = ScriptProcessor(
        image_uri=sklearn_image,
        command=["python3"],
        role=role,
        instance_type=config.PROCESS_INSTANCE_TYPE,
        instance_count=1,
        sagemaker_session=pipeline_session,
    )

    package_args = packager.run(
        code="steps/package.py",
        inputs=[
            # the trained model.tar.gz
            ProcessingInput(
                input_name="model",
                s3_input=ProcessingS3Input(
                    s3_uri=model_artifacts,
                    local_path="/opt/ml/processing/model",
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
            # inference.py and requirements.txt, uploaded above
            ProcessingInput(
                input_name="handler",
                s3_input=ProcessingS3Input(
                    s3_uri=handler_s3_uri,
                    local_path="/opt/ml/processing/handler",
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="packaged",
                s3_output=ProcessingS3Output(
                    s3_uri=f"s3://{bucket}/{config.PREFIX}/packaged",
                    local_path="/opt/ml/processing/packaged",
                    s3_upload_mode="EndOfJob",
                ),
            )
        ],
    )

    step_package = ProcessingStep(
        name="PackageYolo",
        step_args=package_args,
    )

    # the deployable artifact: weights plus code/inference.py
    packaged_dir = (
        step_package.properties.ProcessingOutputConfig.Outputs["packaged"].S3Output.S3Uri
    )
    # ProcessingOutput reports the directory; the registry wants the tarball
    packaged_model = Join(on="/", values=[packaged_dir, "model.tar.gz"])

    # #########################################################
    # 4. EvaluationStep
    # #########################################################
    # construct script processor for eval
    eval_processor = ScriptProcessor(
        image_uri=train_image,
        command=["python3"],
        role=role,
        instance_type=config.PROCESS_INSTANCE_TYPE,
        instance_count=1,
        sagemaker_session=pipeline_session,
    )

    # define eval script
    eval_args = eval_processor.run(
        code="steps/evaluate.py",
        # evaluate at the size the model was trained at
        arguments=["--imgsz", param_imgsz],
        inputs=[
            # model as input
            ProcessingInput(
                input_name="model",
                s3_input=ProcessingS3Input(
                    s3_uri=model_artifacts,
                    local_path="/opt/ml/processing/model",
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
            # split as input
            ProcessingInput(
                input_name="split",
                s3_input=ProcessingS3Input(
                    s3_uri=split_uri,
                    local_path="/opt/ml/processing/split",
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
            # config as input
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
            # eval artifacts as output
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

    # evaluation.json
    evaluation_report = PropertyFile(
        name="EvaluationReport",
        output_name="evaluation",
        path="evaluation.json",
    )

    # define a task to run script
    step_evaluate = ProcessingStep(
        name="EvaluateYolo",
        step_args=eval_args,
        property_files=[evaluation_report],
    )

    # #########################################################
    # 5. Register model
    # #########################################################
    # construct model builder
    model_builder = ModelBuilder(
        s3_model_data_url=packaged_model,
        image_uri=inference_image,
        role_arn=role,
        sagemaker_session=pipeline_session,
    )

    # registers machine learning model into Model Package Group
    register_args = model_builder.register(
        model_package_group_name=config.MODEL_PACKAGE_GROUP,
        content_types=["application/x-image"],
        response_types=["application/json"],
        # serverless endpoints have no instance type; these describe what the
        # package supports, and the deploy pipeline picks the real one
        inference_instances=[config.PROCESS_INSTANCE_TYPE],
        approval_status="PendingManualApproval",
    )

    # define a task to register model
    step_register = ModelStep(
        name="RegisterYolo",
        step_args=register_args,
    )

    # #########################################################
    # 6. ConditionStep: register only when metrics is above threhold
    # #########################################################
    # define condition step
    step_condition = ConditionStep(
        name="CheckMap",
        # condition
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
        # , and the execution still succeeds
        # packaging exists only to feed the registry, so it belongs on this
        # branch: a model below the threshold is never packaged at all
        if_steps=[step_package, step_register],
        else_steps=[], # below the threshold nothing runs
    )

    # return a pipeline class
    return Pipeline(
        name=PIPELINE_NAME,
        sagemaker_session=pipeline_session,
        parameters=[param_epochs, param_imgsz, param_batch, param_min_map],
        steps=[
            step_process, # data process
            step_train, # train model
            step_evaluate, # eval
            step_condition, # gate: package and register only if above threshold
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
    # get parameters
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

    # define pipeline
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

    # execute pipeline
    pipeline.upsert(role_arn=args.role_arn)
    execution = pipeline.start()
    print(f"execution  {execution.arn}")

    if args.no_wait:
        return 0

    execution.wait()
    print("Pipeline finished.")
    return 0


if __name__ == "__main__":
    # entry point; exit if error.
    raise SystemExit(main())
