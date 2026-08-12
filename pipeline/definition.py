"""
Pipeline definition.

Built against the sagemaker v3 SDK, where the pieces are split across packages:
`Pipeline`/`ProcessingStep` come from sagemaker.mlops, parameters and the
processor from sagemaker.core. The v2 `sagemaker.Session` no longer exists --
`PipelineSession` is what defers `.run()` into a step definition instead of
launching a job immediately.

Currently covers step 1 (process data) and step 2 (train). Later steps append
to `steps=[...]`.
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
from sagemaker.core.workflow.parameters import (
    ParameterFloat,
    ParameterInteger,
    ParameterString,
)
from sagemaker.mlops.workflow import CacheConfig, Pipeline, ProcessingStep, TrainingStep
from sagemaker.train import ModelTrainer

from pipeline import _windows_fix, config

# the SDK writes its sm_train.sh driver with CRLF on Windows, which bash in the
# training container cannot parse; must run before any ModelTrainer is built
_windows_fix.apply()

REPO = Path(__file__).resolve().parents[1]

# where the processing container mounts each channel
INPUT_DIR = "/opt/ml/processing/input"
CODE_DIR = "/opt/ml/processing/code"
SPLIT_DIR = "/opt/ml/processing/split"
CONFIG_DIR = "/opt/ml/processing/config"

# training containers mount channels under a different root
TRAIN_SPLIT_DIR = "/opt/ml/input/data/split"
TRAIN_CONFIG_DIR = "/opt/ml/input/data/config"

# re-splitting identical raw data is pure cost, so reuse a matching prior run
CACHE = CacheConfig(enable_caching=True, expire_after="7d")


def build_pipeline(session: PipelineSession | None = None) -> Pipeline:
    """Assemble the pipeline object. Does not create it in AWS."""
    session = session or PipelineSession(default_bucket=config.BUCKET)

    # exposed as parameters so a run can re-split without editing code
    raw_uri = ParameterString(name="RawDataUri", default_value=config.RAW_URI)
    instance_type = ParameterString(
        name="ProcessingInstanceType", default_value="ml.m5.xlarge"
    )
    val_fraction = ParameterFloat(name="ValFraction", default_value=0.2)
    seed = ParameterInteger(name="Seed", default_value=0)
    # 0 means "all pairs" -- a pipeline parameter cannot carry None
    limit = ParameterInteger(name="Limit", default_value=0)

    # training knobs, so a smoke run needs no code change
    training_instance_type = ParameterString(
        name="TrainingInstanceType", default_value="ml.g5.xlarge"
    )
    epochs = ParameterInteger(name="Epochs", default_value=10)
    imgsz = ParameterInteger(name="ImageSize", default_value=640)
    batch = ParameterInteger(name="Batch", default_value=8)

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
            # src/ ships alongside the entry point so it can import data_loader.
            # ScriptProcessor claims the name "code" for the entry point it
            # uploads itself, so this channel needs a different one.
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
        instance_type=training_instance_type,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
    )

    return Pipeline(
        name=config.PIPELINE_NAME,
        parameters=[
            raw_uri,
            instance_type,
            val_fraction,
            seed,
            limit,
            training_instance_type,
            epochs,
            imgsz,
            batch,
        ],
        steps=[step_process, step_train],
        sagemaker_session=session,
    )


def _stage_source() -> str:
    """
    Assemble a flat source directory for the training job.

    Two reasons not to hand `SourceCode` the repo root directly:

    * on Windows the SDK builds S3 keys with os.sep, so a nested entry script
      uploads as a literal "pipeline\\steps/train.py" -- one flat object the
      Linux container cannot find at that path;
    * __pycache__ from a 3.12 interpreter would ship to a 3.11 container.

    So the entry point is copied to the top level with src/ beside it, which is
    the layout its import bootstrap already expects.
    """
    # deliberately outside the repo: it sits under OneDrive, whose sync holds
    # handles open and makes rmtree fail with a PermissionError
    staged = Path(tempfile.gettempdir()) / "sagemaker-yolo-train-src"
    shutil.rmtree(staged, ignore_errors=True)
    staged.mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO / "pipeline" / "steps" / "train.py", staged / "train.py")
    shutil.copy2(REPO / "pipeline" / "requirements-train.txt",
                 staged / "requirements.txt")
    # dirs_exist_ok: rmtree above is best-effort, since a sync client or an
    # editor can hold a handle and leave part of the tree behind
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
) -> TrainingStep:
    """
    Train on the split produced by step 1.

    The two channels are wired from the processing step's outputs rather than
    from literal S3 paths, so SageMaker derives the dependency itself and a
    re-split cannot leave training pointed at a stale prefix.
    """
    outputs = step_process.properties.ProcessingOutputConfig.Outputs

    # the DLC ships torch already; ultralytics is installed on top at job start
    trainer = ModelTrainer(
        training_image=image_uris.retrieve(
            framework="pytorch",
            region=config.REGION,
            version="2.5.1",
            py_version="py311",
            instance_type="ml.g5.xlarge",
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
        # a hung job on a GPU instance is expensive; cap it
        stopping_condition=StoppingCondition(max_runtime_in_seconds=3 * 60 * 60),
        output_data_config=OutputDataConfig(s3_output_path=config.s3("train")),
        base_job_name=f"{config.PIPELINE_NAME}-train",
        role=config.ROLE_ARN,
        sagemaker_session=session,
        # hyperparameter values must be strings; an integer parameter has to be
        # converted explicitly or CreatePipeline rejects the definition
        hyperparameters={
            "epochs": epochs.to_string(),
            "imgsz": imgsz.to_string(),
            "batch": batch.to_string(),
            "split-dir": TRAIN_SPLIT_DIR,
            "config-dir": TRAIN_CONFIG_DIR,
        },
    )

    step_args = trainer.train(
        input_data_config=[
            # channel name "split" matches the path baked into data.yaml by
            # step 1; train.py rewrites it regardless, so the two cannot drift
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
