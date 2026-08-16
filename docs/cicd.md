goal

- create cicd

---

cicd

1. update image

- trigger: train/dockerfile
- push ecr

```sh
terraform -chdir=infra output -raw github_actions_role_arn
gh secret set AWS_ROLE_ARN --body "arn:aws:iam::099139718958:role/sagemaker-yolo-dev-github-actions-role"

```

1. endpoint pipeline

- trigger: train/

3. infra dpeloy

- trigger: infra/, lambda/
