"""
Pipeline definition: process data -> train -> evaluate -> threshold gate.

Built against the sagemaker v3 SDK, where the pieces live in different
packages: Pipeline/ProcessingStep in sagemaker.mlops, parameters and
processors in sagemaker.core. PipelineSession defers `.run()` into a step
definition instead of launching a job.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from sagemaker.core import image_uris
from sagemaker.core.processing import (
    PipelineSession,
    ProcessingInput,
    ProcessingOutput,
    ScriptProcessor,
)
from sagemaker.core.shapes.shapes import ProcessingS3Input, ProcessingS3Output
from sagemaker.core.training.configs import (
    Compute,
    InputData,
    OutputDataConfig,
    SourceCode,
    StoppingCondition,
)
from sagemaker.core.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.core.workflow.functions import Join, JsonGet
from sagemaker.core.workflow.parameters import (
    ParameterFloat,
    ParameterInteger,
    ParameterString,
)
from sagemaker.core.workflow.properties import PropertyFile
from sagemaker.mlops.workflow import (
    CacheConfig,
    ConditionStep,
    FailStep,
    Pipeline,
    ProcessingStep,
    TrainingStep,
)
from sagemaker.train import ModelTrainer

from pipeline import _windows_fix, config

# must run before any ModelTrainer is constructed
_windows_fix.apply()

REPO = Path(__file__).resolve().parents[1]

# container mount points
INPUT_DIR = "/opt/ml/processing/input"
CODE_DIR = "/opt/ml/processing/code"
SPLIT_DIR = "/opt/ml/processing/split"
CONFIG_DIR = "/opt/ml/processing/config"

# training containers use a different root
TRAIN_SPLIT_DIR = "/opt/ml/input/data/split"
TRAIN_CONFIG_DIR = "/opt/ml/input/data/config"

EVAL_MODEL_DIR = "/opt/ml/processing/model"
EVAL_OUTPUT_DIR = "/opt/ml/processing/evaluation"

CACHE = CacheConfig(enable_caching=True, expire_after="7d")


def build_pipeline(
    session: PipelineSession | None = None,
    training_instance_type: str = "ml.m5.xlarge",
) -> Pipeline:
    """
    Assemble the pipeline object. Does not create it in AWS.

    `training_instance_type` is a plain string, not a pipeline parameter,
    because it also selects the training image and the ultralytics device --
    both fixed when the definition is built. Changing it needs a re-upsert.
    """
    session = session or PipelineSession(default_bucket=config.BUCKET)

    # g4dn/g5/p* are the GPU families; anything else trains on CPU
    is_gpu = training_instance_type.split(".")[1].startswith(("g", "p"))

    raw_uri = ParameterString(name="RawDataUri", default_value=config.RAW_URI)
    instance_type = ParameterString(
        name="ProcessingInstanceType", default_value="ml.m5.xlarge"
    )
    val_fraction = ParameterFloat(name="ValFraction", default_value=0.2)
    seed = ParameterInteger(name="Seed", default_value=0)
    # 0 means "all pairs" -- a pipeline parameter cannot carry None
    limit = ParameterInteger(name="Limit", default_value=0)

    training_instance = ParameterString(
        name="TrainingInstanceType", default_value=training_instance_type
    )
    epochs = ParameterInteger(name="Epochs", default_value=10)
    imgsz = ParameterInteger(name="ImageSize", default_value=640)
    batch = ParameterInteger(name="Batch", default_value=8)

    min_map = ParameterFloat(name="MinMap", default_value=0.70)

    # sklearn image is just a python runtime here; the split needs no ML deps
    processor = ScriptProcessor(
        image_uri=image_uris.retrieve(
            framework="sklearn",
            region=config.REGION,
            version="1.2-1",
            py_version="py3",
            instance_type="ml.m5.xlarge",
        ),
        command=["python3"],
        instance_type=instance_type,
        instance_count=1,
        base_job_name=f"{config.PIPELINE_NAME}-preprocess",
        role=config.ROLE_ARN,
        sagemaker_session=session,
    )

    step_args = processor.run(
        code="pipeline/steps/preprocess.py",
        inputs=[
            ProcessingInput(
                input_name="raw",
                s3_input=ProcessingS3Input(
                    s3_uri=raw_uri,
                    local_path=INPUT_DIR,
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
            # not "code": ScriptProcessor reserves that name for the entry point
            ProcessingInput(
                input_name="src",
                s3_input=ProcessingS3Input(
                    s3_uri=config.s3("code", "src"),
                    local_path=f"{CODE_DIR}/src",
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="split",
                s3_output=ProcessingS3Output(
                    s3_uri=config.s3("split"),
                    local_path=SPLIT_DIR,
                    s3_upload_mode="EndOfJob",
                ),
            ),
            # data.yaml + preprocess.json, consumed by the training step
            ProcessingOutput(
                output_name="config",
                s3_output=ProcessingS3Output(
                    s3_uri=config.s3("config"),
                    local_path=CONFIG_DIR,
                    s3_upload_mode="EndOfJob",
                ),
            ),
        ],
        arguments=[
            "--input-dir", INPUT_DIR,
            "--split-dir", SPLIT_DIR,
            "--config-dir", CONFIG_DIR,
            "--val-fraction", val_fraction.to_string(),
            "--seed", seed.to_string(),
            "--limit", limit.to_string(),
        ],
    )

    step_process = ProcessingStep(
        name="ProcessData",
        step_args=step_args,
        cache_config=CACHE,
    )

    step_train = _train_step(
        session=session,
        step_process=step_process,
        instance_type=training_instance,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        image_instance_type=training_instance_type,
        device="0" if is_gpu else "cpu",
    )

    step_evaluate, step_gate = _evaluate_step(
        session=session,
        step_process=step_process,
        step_train=step_train,
        instance_type=instance_type,
        imgsz=imgsz,
        min_map=min_map,
    )

    return Pipeline(
        name=config.PIPELINE_NAME,
        parameters=[
            raw_uri,
            instance_type,
            val_fraction,
            seed,
            limit,
            training_instance,
            epochs,
            imgsz,
            batch,
            min_map,
        ],
        steps=[step_process, step_train, step_evaluate, step_gate],
        sagemaker_session=session,
    )


def _evaluate_step(
    session: PipelineSession,
    step_process: ProcessingStep,
    step_train: TrainingStep,
    instance_type: ParameterString,
    imgsz: ParameterInteger,
    min_map: ParameterFloat,
) -> ConditionStep:
    """
    Score the trained weights and gate the pipeline on the result.

    The model is re-scored rather than read from the training job's
    summary.json, so a checkpoint that disagrees with its reported metrics is
    caught before anything downstream trusts it.

    Returns (evaluate_step, condition_step).
    """
    outputs = step_process.properties.ProcessingOutputConfig.Outputs

    processor = ScriptProcessor(
        # pytorch image for torch; scoring does not need a GPU
        image_uri=image_uris.retrieve(
            framework="pytorch",
            region=config.REGION,
            version="2.5.1",
            py_version="py311",
            instance_type="ml.m5.xlarge",
            image_scope="training",
        ),
        command=["python3"],
        instance_type=instance_type,
        instance_count=1,
        base_job_name=f"{config.PIPELINE_NAME}-evaluate",
        role=config.ROLE_ARN,
        sagemaker_session=session,
    )

    step_args = processor.run(
        code="pipeline/steps/evaluate.py",
        inputs=[
            ProcessingInput(
                input_name="model",
                s3_input=ProcessingS3Input(
                    s3_uri=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                    local_path=EVAL_MODEL_DIR,
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
            ProcessingInput(
                input_name="split",
                s3_input=ProcessingS3Input(
                    s3_uri=outputs["split"].S3Output.S3Uri,
                    local_path=SPLIT_DIR,
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
            ProcessingInput(
                input_name="src",
                s3_input=ProcessingS3Input(
                    s3_uri=outputs["config"].S3Output.S3Uri,
                    local_path=CONFIG_DIR,
                    s3_data_type="S3Prefix",
                    s3_input_mode="File",
                ),
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="evaluation",
                s3_output=ProcessingS3Output(
                    s3_uri=config.s3("evaluation"),
                    local_path=EVAL_OUTPUT_DIR,
                    s3_upload_mode="EndOfJob",
                ),
            ),
        ],
        arguments=[
            "--model-dir", EVAL_MODEL_DIR,
            "--split-dir", SPLIT_DIR,
            "--config-dir", CONFIG_DIR,
            "--output-dir", EVAL_OUTPUT_DIR,
            "--imgsz", imgsz.to_string(),
            "--min-map", min_map.to_string(),
        ],
    )

    # exposes evaluation.json to the condition below
    report = PropertyFile(
        name="EvaluationReport",
        output_name="evaluation",
        path="evaluation.json",
    )

    step_evaluate = ProcessingStep(
        name="EvaluateModel",
        step_args=step_args,
        property_files=[report],
        cache_config=CACHE,
    )

    # compares the score, not the script's boolean, so MinMap stays overridable
    condition = ConditionGreaterThanOrEqualTo(
        left=JsonGet(
            step_name=step_evaluate.name,
            property_file=report,
            json_path="mAP50-95",
        ),
        right=min_map,
    )

    step_condition = ConditionStep(
        name="CheckThreshold",
        conditions=[condition],
        if_steps=[],
        else_steps=[
            FailStep(
                name="ModelBelowThreshold",
                error_message=Join(
                    on="",
                    values=[
                        "mAP50-95 below the minimum of ",
                        min_map.to_string(),
                        "; see ",
                        config.s3("evaluation"),
                        "/evaluation.json",
                    ],
                ),
            )
        ],
    )

    # both: the compiler resolves JsonGet by step name, so EvaluateModel must
    # also be listed in the pipeline
    return step_evaluate, step_condition


def _stage_source() -> str:
    """
    Assemble a flat source directory for the training job.

    train.py sits at the top with src/ beside it. The nesting matters: on
    Windows the SDK builds S3 keys with os.sep, so a nested entry script
    uploads as a single object named "pipeline\\steps/train.py".
    """
    # outside the repo: OneDrive holds handles open and breaks rmtree
    staged = Path(tempfile.gettempdir()) / "sagemaker-yolo-train-src"
    shutil.rmtree(staged, ignore_errors=True)
    staged.mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO / "pipeline" / "steps" / "train.py", staged / "train.py")
    shutil.copy2(REPO / "pipeline" / "requirements-train.txt",
                 staged / "requirements.txt")
    shutil.copytree(
        REPO / "src",
        staged / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        dirs_exist_ok=True,
    )
    return str(staged)


def _train_step(
    session: PipelineSession,
    step_process: ProcessingStep,
    instance_type: ParameterString,
    epochs: ParameterInteger,
    imgsz: ParameterInteger,
    batch: ParameterInteger,
    image_instance_type: str,
    device: str,
) -> TrainingStep:
    """
    Train on the split produced by step 1.

    Channels are wired from the processing step's outputs rather than literal
    S3 paths, so SageMaker derives the dependency and a re-split cannot leave
    training on a stale prefix.
    """
    outputs = step_process.properties.ProcessingOutputConfig.Outputs

    # the DLC ships torch; ultralytics installs on top at job start
    trainer = ModelTrainer(
        # the image is fixed at definition time while instance_type resolves at
        # runtime, so image_instance_type has to be set to match
        training_image=image_uris.retrieve(
            framework="pytorch",
            region=config.REGION,
            version="2.5.1",
            py_version="py311",
            instance_type=image_instance_type,
            image_scope="training",
        ),
        source_code=SourceCode(
            source_dir=_stage_source(),
            entry_script="train.py",
            requirements="requirements.txt",
        ),
        compute=Compute(
            instance_type=instance_type,
            instance_count=1,
            volume_size_in_gb=50,
        ),
        stopping_condition=StoppingCondition(max_runtime_in_seconds=3 * 60 * 60),
        output_data_config=OutputDataConfig(s3_output_path=config.s3("train")),
        base_job_name=f"{config.PIPELINE_NAME}-train",
        role=config.ROLE_ARN,
        sagemaker_session=session,
        # to_string() is required: hyperparameter values must be strings
        hyperparameters={
            "epochs": epochs.to_string(),
            "imgsz": imgsz.to_string(),
            "batch": batch.to_string(),
            "device": device,
            "split-dir": TRAIN_SPLIT_DIR,
            "config-dir": TRAIN_CONFIG_DIR,
        },
    )

    step_args = trainer.train(
        input_data_config=[
            InputData(
                channel_name="split",
                data_source=outputs["split"].S3Output.S3Uri,
            ),
            InputData(
                channel_name="config",
                data_source=outputs["config"].S3Output.S3Uri,
            ),
        ],
        wait=False,
    )

    return TrainingStep(
        name="TrainModel",
        step_args=step_args,
        cache_config=CACHE,
    )
