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

### 5. hyperparamter tunning

- train model with mlflow hyperparameter
- hyperparameter tunning with train-mlflow-hyperparam.ipynb
- output model in s3 trains/models

