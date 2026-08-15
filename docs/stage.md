stage: refactor

1. train job

- how to export hyperparameter from mlflow and integrate with train job pipeline

train/hyperparams.json
config.py
pipeline.py
train.py
evaluate.py


2. inference

- now the inference it is baked in the train.py which is part of train job, not inference jobs.

1. Delete deploy/code/inference.py and deploy/package.py

Both are dead. Removing them leaves exactly one handler.

2. Move train/steps/inference.py → deploy/code/inference.py

Same file, new home. Move requirements-inference.txt alongside it as requirements.txt. Nothing about the code changes — it's correct.

3. Delete lines 98-110 from train.py

The shutil.copy2 calls that inject code/ into /opt/ml/model/. train.py keeps: training, ONNX export, the metadata sidecar. It loses all knowledge that serving exists.

4. Add a PackageYolo ProcessingStep to pipeline.py

Between TrainYolo and the register step:

input: model_artifacts (the training output tarball)
source_dir: deploy/code
script: unpack the tar, add code/inference.py + code/requirements.txt, retar
output: new model.tar.gz at s3://{bucket}/{PREFIX}/packaged
Then point ModelBuilder's s3_model_data_url at that output instead of model_artifacts.

Cost: one ml.m5.large job, ~1 minute per pipeline run.

5. Pin end2end=True in the export call, record it in the sidecar

train.py:90 currently relies on the default. Pass it explicitly and add "end2end": True to model.metadata.json. Cheap insurance against an ultralytics bump.