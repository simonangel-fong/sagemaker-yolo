goal

- create cicd

---

cicd

## Lambda Image workflow

- name: build lambda image
- Trigger:
  - workflow
  - lambda/
  - manual
- key steps:
  - Login AWS
  - Build and push
  - Summary report

---

## Train Image workflow

- name: build train image
- Trigger:
  - workflow
  - train/
  - manual
- key steps:
  - Login AWS
  - Build and push
  - Summary report

---

## Infra deploy workflow

- name: infrastructure deploy
- Trigger:
  - infra/
  - manual
- key steps:
  - Setup terraform
  - Setup aws
  - Terraform init
  - Terraform fmt
  - Terraform validate
  - Terraform plan
  - Terraform apply
  - Summary report

---

## Infra destroy workflow

- name: infrastructure destroy
- Trigger:
  - manual
- key steps:
  - Setup terraform
  - Setup aws
  - Terraform init
  - Terraform fmt
  - Terraform validate
  - Terraform plan
  - Terraform destroy
  - Summary report

---

## GitHub Action variables and secrets

| Variables | Description |
| --------- | ----------- |
|           |             |

| Secrets | Description |
| ------- | ----------- |
|         |             |

```sh
terraform -chdir=infra output -raw github_actions_role_arn
gh secret set AWS_ROLE_ARN --body "arn:aws:iam::099139718958:role/sagemaker-yolo-dev-github-actions-role"

```
