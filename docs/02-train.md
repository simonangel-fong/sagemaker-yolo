# Sagemaker yolo - Training

[Back](../README.md)

- [Sagemaker yolo - Training](#sagemaker-yolo---training)
  - [Upload raw data](#upload-raw-data)
  - [Enable experiment](#enable-experiment)

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

## Enable experiment

- experiment environment is controled by variable `enable_experiment`

```sh
# apply
terraform -chdir=infra apply -auto-approve -var="enable_experiment=true"

# Notebook
terraform -chdir=infra output -raw notebook_url

# MLflow
aws sagemaker create-presigned-mlflow-tracking-server-url \
  --tracking-server-name sagemaker-yolo-dev \
  --region ca-central-1 --query AuthorizedUrl --output text
```
