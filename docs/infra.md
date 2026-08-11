```sh
terraform -chdir=infra init -backend-config=backend.hcl

terraform -chdir=infra fmt && terraform -chdir=infra validate
terraform -chdir=infra plan

terraform -chdir=infra apply -auto-approve
terraform -chdir=infra destroy -auto-approve

terraform -chdir=infra refresh
terraform -chdir=infra output
```
