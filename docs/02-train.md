# Sagemaker yolo - Training

[Back](../README.md)

- [Sagemaker yolo - Training](#sagemaker-yolo---training)
  - [Upload raw data](#upload-raw-data)
  - [Hyperparameters](#hyperparameters)
  - [Sweep](#sweep)
  - [Notebook](#notebook)
  - [MLflow](#mlflow)

---

## Upload raw data

```sh
terraform -chdir=infra output -raw s3_sync_command
# aws s3 sync data/raw s3://sagemaker-yolo-dev-up68ac/raw-data/

# sync raw data
aws s3 sync data/raw s3://sagemaker-yolo-dev-up68ac/raw-data/

# remove a folder
aws s3 rm s3://sagemaker-yolo-dev-up68ac/raw-data/ --recursive
```

---

## Hyperparameters

`train/hyperparams.json` is the contract between the sweep and the pipeline:

```json
{
  "schema": 1,
  "hyperparameters": { "epochs": 50, "imgsz": 640, "batch": 8, "seed": 0 },
  "provenance": { "run_id": "ed580a66...", "metric": "mAP50-95", "value": 0.8276 }
}
```

The sweep notebook writes it, git carries it, the pipeline reads it. **The
pipeline never queries MLflow**, so the tracking server only has to run while a
sweep is actually happening.

- `hyperparameters` goes straight to the training job. Keys beyond
  `epochs`/`imgsz`/`batch` are forwarded to YOLO untouched, so widening the
  sweep needs no code change.
- `provenance` records which run chose the values. It is stamped onto
  `model.metadata.json` so the artifact stays traceable after the server is
  gone.

A malformed file fails in seconds with a message naming the problem, rather than
training for an hour on the wrong config.

---

## Sweep

Run this only when the hyperparameters need to change. The tracking server costs
money while it is up, so it is destroyed again afterwards.

```sh
# 1. bring up the notebook and the tracking server
terraform -chdir=infra apply -var enable_experiment=true

# 2. run notebook/03-train-mlflow-sweep.ipynb in Studio
terraform -chdir=infra output -raw notebook_url
```

The notebook's **Export hyperparameters** cell writes `train/hyperparams.json`.
Commit it from Studio:

```sh
git add train/hyperparams.json
git commit -m "train: hyperparameters from sweep"
git push
```

```sh
# 3. tear the server back down
terraform -chdir=infra apply -var enable_experiment=false
```

Training now runs off the committed file. See [03-pipeline.md](03-pipeline.md)
for the pipeline itself.

Override a run without touching the file:

```sh
# validate and print the definition, no AWS writes
python pipeline.py --role-arn ... --bucket ... --train-image ... --dry-run

# short smoke run
python pipeline.py --role-arn ... --bucket ... --train-image ... --epochs 3

# start and exit, for CI
python pipeline.py --role-arn ... --bucket ... --train-image ... --no-wait
```

`epochs`, `imgsz` and `batch` are also pipeline parameters, so a single
execution can be overridden from the console or with
`pipeline.start(parameters={"Epochs": 3})`.

---

## Notebook

```sh
terraform -chdir=infra output -raw notebook_url
```

---

## MLflow

Only reachable while `enable_experiment=true`.

```sh
# presigned UI url
aws sagemaker create-presigned-mlflow-tracking-server-url \
  --tracking-server-name sagemaker-yolo-dev \
  --region ca-central-1 --query AuthorizedUrl --output text
```

The `mlflow_ui_command` and `mlflow_tracking_server_arn` outputs are commented
out in `infra/04-outputs-experiment.tf`; uncomment them to get these by
`terraform output` instead.
