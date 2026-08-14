# Stage 7. pipeline

## Goal

- create pipeline with python sdk

---

## Stack

- aws sagemaker
- python SDK sagemaker v3

---

## Constrain

- use sagemaker codes as much as possible
- train job runs independently, no reference codes in other dir.

---

## steps

| #   | steps                                       |
| --- | ------------------------------------------- |
| 1   | rewrite preprocess, pipeline                |
| 2   | test preprocess job                         |
| 3   | create train docker image, rewrite train.py |
| 4   | test locally with small size                |
| 5   | push image                                  |
| 6   | rewrite pipeline                            |
| 7   | test train job                              |
| 8   | rewrite evaluate, pipeline                  |
| 9   | test pipeline                               |
| 10  | register model                              |
| 11  | deploy serverless endpoint                  |
