# Sagemaker yolo - Training

[Back](../README.md)

- [Sagemaker yolo - Training](#sagemaker-yolo---training)
  - [Upload raw data](#upload-raw-data)
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

## Notebook

```sh
terraform -chdir=infra output -raw notebook_url
```

---

## MLflow

```sh
# login mlflow ui command
terraform -chdir=infra output -raw mlflow_ui_command
```
