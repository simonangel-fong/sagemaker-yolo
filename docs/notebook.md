
## Login

```sh
terraform -chdir=infra output -raw notebook_url
```



```sh
terraform -chdir=infra output -raw s3_sync_command
# aws s3 sync data/raw s3://sagemaker-yolo-dev-0luf20/data/raw

# sync raw data
aws s3 sync data/raw s3://sagemaker-yolo-dev-0luf20/data/raw

# remove a folder
aws s3 rm s3://sagemaker-yolo-dev-vh4wix/data/raw --recursive
```

---

## MLflow

```sh
# login mlflow ui command
terraform -chdir=infra output -raw mlflow_ui_command


```