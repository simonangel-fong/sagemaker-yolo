# pipeline.py
# the script define pipeline

from sagemaker.core.helper.session_helper import Session, get_execution_role
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
from sagemaker.train.configs import InputData, Compute

from sagemaker.mlops.workflow.pipeline import Pipeline
from sagemaker.mlops.workflow.steps import ProcessingStep, TrainingStep
from sagemaker.serve.model_builder import ModelBuilder
from sagemaker.mlops.workflow.model_step import ModelStep


INPUT_S3_URI = "s3://sagemaker-yolo-dev-up68ac/raw-data/"
MODEL_PACKAGE_GROUP = "sagemaker-yolo"
PREFIX = "train-pipeline"


session = Session()
pipeline_session = PipelineSession()

region = session.boto_region_name
role = get_execution_role()
bucket = session.default_bucket()


# ---------------------------------------------------------
# Shared sklearn image
# ---------------------------------------------------------

sklearn_image = image_uris.retrieve(
    framework="sklearn",
    region=region,
    version="1.2-1",
    py_version="py3",
    instance_type="ml.m5.large",
)


# #########################################################
# 1. ProcessingStep
# #########################################################
processor = ScriptProcessor(
    image_uri=sklearn_image,
    command=["python3"],
    role=role,
    instance_type="ml.m5.large",
    instance_count=1,
    sagemaker_session=pipeline_session,
)

process_args = processor.run(
    code="steps/preprocess.py",
    inputs=[
        ProcessingInput(
            input_name="yolo",
            s3_input=ProcessingS3Input(
                s3_uri=INPUT_S3_URI,
                local_path="/opt/ml/processing/input",
                s3_data_type="S3Prefix",
                s3_input_mode="File",
            ),
        )
    ],
    outputs=[
        ProcessingOutput(
            output_name="train",
            s3_output=ProcessingS3Output(
                s3_uri=f"s3://{bucket}/{PREFIX}/train",
                local_path="/opt/ml/processing/train",
                s3_upload_mode="EndOfJob",
            ),
        ),
        ProcessingOutput(
            output_name="validation",
            s3_output=ProcessingS3Output(
                s3_uri=f"s3://{bucket}/{PREFIX}/validation",
                local_path="/opt/ml/processing/validation",
                s3_upload_mode="EndOfJob",
            ),
        ),
    ],
)

step_process = ProcessingStep(
    name="ProcessIris",
    step_args=process_args,
)


# # #########################################################
# # 2. TrainingStep
# # #########################################################

# trainer = ModelTrainer(
#     training_image=sklearn_image,
#     role=role,
#     compute=Compute(
#         instance_type="ml.m5.large",
#         instance_count=1,
#     ),
#     sagemaker_session=pipeline_session,
#     input_data_config=[
#         InputData(
#             channel_name="train",
#             data_source=(
#                 step_process
#                 .properties
#                 .ProcessingOutputConfig
#                 .Outputs["train"]
#                 .S3Output
#                 .S3Uri
#             ),
#             content_type="text/csv",
#         )
#     ],
# )

# train_args = trainer.train(
#     source_dir="code",
#     entry_script="train.py",
# )

# step_train = TrainingStep(
#     name="TrainIris",
#     step_args=train_args,
# )


# # ---------------------------------------------------------
# # 3. EvaluationStep
# # ---------------------------------------------------------

# eval_processor = ScriptProcessor(
#     image_uri=sklearn_image,
#     command=["python3"],
#     role=role,
#     instance_type="ml.m5.large",
#     instance_count=1,
#     sagemaker_session=pipeline_session,
# )

# eval_args = eval_processor.run(
#     code="code/evaluate.py",
#     inputs=[
#         ProcessingInput(
#             input_name="model",
#             s3_input=ProcessingS3Input(
#                 s3_uri=(
#                     step_train
#                     .properties
#                     .ModelArtifacts
#                     .S3ModelArtifacts
#                 ),
#                 local_path="/opt/ml/processing/model",
#                 s3_data_type="S3Prefix",
#                 s3_input_mode="File",
#             ),
#         ),
#         ProcessingInput(
#             input_name="validation",
#             s3_input=ProcessingS3Input(
#                 s3_uri=(
#                     step_process
#                     .properties
#                     .ProcessingOutputConfig
#                     .Outputs["validation"]
#                     .S3Output
#                     .S3Uri
#                 ),
#                 local_path="/opt/ml/processing/validation",
#                 s3_data_type="S3Prefix",
#                 s3_input_mode="File",
#             ),
#         ),
#     ],
#     outputs=[
#         ProcessingOutput(
#             output_name="evaluation",
#             s3_output=ProcessingS3Output(
#                 s3_uri=f"s3://{bucket}/{PREFIX}/evaluation",
#                 local_path="/opt/ml/processing/evaluation",
#                 s3_upload_mode="EndOfJob",
#             ),
#         )
#     ],
# )

# step_evaluate = ProcessingStep(
#     name="EvaluateIris",
#     step_args=eval_args,
# )


# # ---------------------------------------------------------
# # 4. Register model
# # ---------------------------------------------------------

# model_builder = ModelBuilder(
#     s3_model_data_url=(
#         step_train
#         .properties
#         .ModelArtifacts
#         .S3ModelArtifacts
#     ),
#     image_uri=sklearn_image,
#     role_arn=role,
#     sagemaker_session=pipeline_session,
# )

# register_args = model_builder.register(
#     model_package_group_name=MODEL_PACKAGE_GROUP,
#     content_types=["text/csv"],
#     response_types=["application/json"],
#     inference_instances=["ml.m5.large"],
#     approval_status="PendingManualApproval",
# )

# step_register = ModelStep(
#     name="RegisterIrisModel",
#     step_args=register_args,
# )

# # NOTE:
# # This minimal file registers after evaluation.
# # Add a ConditionStep later if you want:
# #     accuracy >= threshold -> register
# #     otherwise -> stop


# #########################################################
# Pipeline
# #########################################################
pipeline = Pipeline(
    name="sakemaker-yolo-pipeline",
    sagemaker_session=pipeline_session,
    steps=[
        step_process,
        # step_train,
        # step_evaluate,
        # step_register,
    ],
)


if __name__ == "__main__":
    pipeline.upsert(role_arn=role)

    execution = pipeline.start()
    execution.wait()

    print("Pipeline finished.")
