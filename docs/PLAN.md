# Plan - stage 2 Train model

## Goal

- train model in train.ipynb
- output model in s3 trains/models

---

## Stack

- AWS Sagemaker
- notebook is enabled in sagemaker studio

---

## Phases

| #   | Phase                                                                                            |
| --- | ------------------------------------------------------------------------------------------------ |
| 1   | create train.ipynb                                                                               |
| 2   | add `environment` section where inspect the environment                                          |
| 3   | add `data processing` section where inspect data, split data, sync split data to data/processed/ |
| 4   | add `define model` section where model is defined                                                |
| 5   | add `train model` section where parameters is defined and model is trained                       |
| 6   | add `eval model` section where model is evaluate                                                 |
| 7   | add `export model` section where model is exported to s3                                         |
