```sh
terraform -chdir=infra init -backend-config=backend.hcl

terraform -chdir=infra fmt && terraform -chdir=infra validate
terraform -chdir=infra plan

terraform -chdir=infra apply -auto-approve
terraform -chdir=infra destroy -auto-approve

terraform -chdir=infra refresh
terraform -chdir=infra output
```

```sh
terraform -chdir=infra output -raw s3_sync_command
# aws s3 sync data/raw s3://sagemaker-yolo-dev-0luf20/data/raw

# sync raw data
aws s3 sync data/raw s3://sagemaker-yolo-dev-0luf20/data/raw

# remove a folder
aws s3 rm s3://sagemaker-yolo-dev-vh4wix/data/raw --recursive
```