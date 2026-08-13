## Stages

### 1. init notebook

- init infra via terraform

---

### 2. Train model

- train model in train.ipynb
- output model in s3 trains/models

---

### 3. init mlflow

- init mlflow in sagemaker

---

### 4. track model training

- enable tracking in sagemaker
- train and track model with train-mlflow.ipynb
- output model in s3 trains/models

---

### 5. hyperparamter sweep

- train model with mlflow hyperparameter
- hyperparameter sweep with train-mlflow-sweep.ipynb
- output model in s3 trains/models

---

### 6. gpu notebook server(hold)

- create train-mlflow-sweep-cpu-vs-gpu.ipynb
- sweep with cpu and gpu

---

### 7. pipeline(halt)

- create pipeline with python sdk

---

### 8. deployment

- create model in sagemaker
- create inference endpoint serverless
- test