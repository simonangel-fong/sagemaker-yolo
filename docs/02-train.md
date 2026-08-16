# Sagemaker yolo - Training

[Back](../README.md)

- [Sagemaker yolo - Training](#sagemaker-yolo---training)
  - [Upload raw data](#upload-raw-data)
  - [Enable experiment](#enable-experiment)
    - [Notebook](#notebook)
    - [MLflow sweep](#mlflow-sweep)
    - [Device GPU](#device-gpu)
  - [Comparison: CPU vs GPU](#comparison-cpu-vs-gpu)

---

## Upload raw data

```sh
# get sync command
terraform -chdir=infra output -raw s3_sync_command
# aws s3 sync data/raw s3://sagemaker-yolo-dev-up68ac/raw-data/

# sync raw data
aws s3 sync data/raw s3://sagemaker-yolo-dev-up68ac/raw-data/

# list
aws s3 ls s3://sagemaker-yolo-dev-up68ac/raw-data/ --recursive

# remove a folder
aws s3 rm s3://sagemaker-yolo-dev-up68ac/raw-data/ --recursive
```

---

## Enable experiment

- experiment environment is controled by variable `enable_experiment`

```sh
# apply
terraform -chdir=infra apply -auto-approve -var="enable_experiment=true"

# studio domain login
terraform -chdir=infra output -raw studio_login_command
# Notebook
terraform -chdir=infra output -raw notebook_url

# MLflow
aws sagemaker create-presigned-mlflow-tracking-server-url \
  --tracking-server-name sagemaker-yolo-dev \
  --region ca-central-1 --query AuthorizedUrl --output text
```

---

### Notebook

- Train with cpu

![notebook_train_cpu01](./img/notebook_train_cpu01.png)

![notebook_train_sweep01](./img/notebook_train_sweep01.png)

- val: accept model

![notebook_val_accept01](./img/notebook_val_accept01.png)

- val: reject model

![notebook_val_reject01](./img/notebook_val_reject01.png)

---

### MLflow sweep

- Experiments with mlflow server

![sagemaker_experiment01](./img/sagemaker_experiment01.png)

- learning rate

![mlflow_lr01](./img/mlflow_lr01.png)

- loss

![mlflow_loss01](./img/mlflow_loss01.png)

- mPA

![mlflow_metrics01](./img/mlflow_metrics01.png)

- precision & recall

![mlflow_metrics02](./img/mlflow_metrics02.png)

- val

![mlflow_val01](./img/mlflow_val01.png)

- train time

![mlflow_traintime01](./img/mlflow_traintime01.png)

---

### Device GPU

- gpu info

![gpu_info01](./img/gpu_info01.png)

![gpu_info02](./img/gpu_info02.png)

![gpu_info03](./img/gpu_info03.png)

---

- train with cpu

![cpu_vs_gpu_cmd_cpu01](./img/cpu_vs_gpu_cmd_cpu01.png)

![cpu_vs_gpu_cmd_cpu02](./img/cpu_vs_gpu_cmd_cpu02.png)

- train with gpu

![cpu_vs_gpu_cmd_gpu01](./img/cpu_vs_gpu_cmd_gpu01.png)

![cpu_vs_gpu_cmd_gpu02](./img/cpu_vs_gpu_cmd_gpu02.png)

---

## Comparison: CPU vs GPU

- epoch: 10

| instance              | Specification | rate_per_hour($) | total_min | total_usd($) |
| --------------------- | ------------- | ---------------- | --------- | ------------ |
| `ml.m5.xlarge(CPU)`   | 4vCPU, 16 GiB | 0.257            | 27.8      | 0.379        |
| `ml.g4dn.xlarge(GPU)` | 4vCPU, 16 GiB | 0.818            | 2.2       | 0.029        |

- train time

![cpu_vs_gpu_cmd_gpu03](./img/cpu_vs_gpu01.png)

- cpu% vs gpu%

![cpu_vs_gpu02](./img/cpu_vs_gpu02.png)
