# License plate recognition with `Amazon SageMaker`

An `Amazon SageMaker` project that trains and deploys a object detection model(`YOLO`) with `MLOps` workflow.

![Terraform](https://img.shields.io/badge/Terraform-7B42BC?style=for-the-badge&logo=terraform&logoColor=white&style=plastic) ![AWS](https://img.shields.io/badge/AWS-FF9900?style=for-the-badge&logo=amazonwebservices&logoColor=white&style=plastic) ![Cloudflare](https://img.shields.io/badge/Cloudflare-F38020?style=for-the-badge&logo=Cloudflare&logoColor=white&style=plastic) ![GitHub](https://img.shields.io/badge/github-%23121011.svg?style=for-the-badge&logo=github&logoColor=white&style=plastic) ![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white&style=plastic) ![YOLO](https://img.shields.io/badge/YOLO-111F68?logo=yolo&logoColor=fff&style=plastic) ![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=fff&style=plastic)

- [License plate recognition with `Amazon SageMaker`](#license-plate-recognition-with-amazon-sagemaker)
  - [Business Challenge](#business-challenge)
  - [License plate recognition application](#license-plate-recognition-application)
  - [Model training with `Amazon Sagemaker Studio`](#model-training-with-amazon-sagemaker-studio)
    - [MLops Pipeline](#mlops-pipeline)
    - [`Jupyter notebook` \& `MLflow`](#jupyter-notebook--mlflow)
    - [Comparison: `cpu` vs `gpu`](#comparison-cpu-vs-gpu)
  - [Inference deployment](#inference-deployment)

---

## Business Challenge

Computer vision models like `YOLO` are popular for object detection in manufacturing.

> However, integrating this computer vision models reliably into business applications remains a significant challenge.

This project demonstrates an end-to-end MLOps workflow by training, deploying, and serving a a `YOLO` model to detect vehicle plate.

---

## License plate recognition application

- Architecture diagram

![architecture](./docs/img/architecture.png)

- Application

![yolo_plate_detect01](./docs/img/yolo_plate_detect01.png)

> OCR feature is not included

---

## Model training with `Amazon Sagemaker Studio`

Train the `YOLO` model with `Amazon Sagemaker Studio`

### MLops Pipeline

1. Data Collection: collect images of license plate
2. Feature Engineering: label images
3. Model Training and Experiment Tracking: Run training code with `Sagemaker pipeline` and log metrics by `MLflow`
4. Evaluate model
5. Package and deploy model: Serve model with `Sagemaker serverless endpoint` and integrate it with web application.
6. Integrate **inference endpoint** with **web application**.

- Sagemaker pipeline to automate training

![sagemaker_pipeline02](./docs/img/sagemaker_pipeline02.png)

---

### `Jupyter notebook` & `MLflow`

- `Jupyter notebook`: train `YOLO` model

![notebook_train_cpu01](./docs/img/notebook_train_cpu01.png)

- `MLflow`: track training metrics

![mlflow_metrics01](./docs/img/mlflow_metrics01.png)

- `MLflow`: hyperparameter sweep for the best performance

![mlflow_traintime01](./docs/img/mlflow_traintime01.png)

---

### Comparison: `cpu` vs `gpu`

Train the same YOLO model with same dataset and same hyperparameters.

- Cost comparision

| Instance              | Specification | GPU | Rate per hour($) | Total min | Total cost($) |
| --------------------- | ------------- | --- | ---------------- | --------- | ------------- |
| `ml.m5.xlarge(cpu)`   | 4vCPU, 16 GiB | N/A | 0.257            | 27.8      | 0.379         |
| `ml.g4dn.xlarge(gpu)` | 4vCPU, 16 GiB | Yes | 0.818            | 2.2       | 0.029         |

- train time
  - train with cpu: 27.8m
  - train with gpu: 2.2m

![cpu_vs_gpu01](./docs/img/cpu_vs_gpu01.png)

- resources consumption
  - train with cpu (blue): ~75% cpu
  - train with gpu (red): ~75% cpu, gpu: ~15%

![cpu_vs_gpu02](./docs/img/cpu_vs_gpu02.png)

---

## Inference deployment

1. Promote models
2. serve promoted model with Sagemaker serverless endpoint.
3. integrate endpoint with web application
