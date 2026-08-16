# Sagemaker yolo - Terraform

[Back](../README.md)

- [Sagemaker yolo - Terraform](#sagemaker-yolo---terraform)
  - [Infra as code](#infra-as-code)

---

## Infra as code

```sh
terraform -chdir=infra init -backend-config=backend.hcl

terraform -chdir=infra fmt && terraform -chdir=infra validate
terraform -chdir=infra plan

# project
terraform -chdir=infra apply -auto-approve
# experiment enabled
terraform -chdir=infra apply -auto-approve -var="enable_experiment=true"
# deploy enabled
terraform -chdir=infra apply -auto-approve -var="enable_deploy=true"
terraform -chdir=infra destroy -auto-approve

terraform -chdir=infra refresh
terraform -chdir=infra output
```

![architecture](./img/architecture.gif)
