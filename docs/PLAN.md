# Stage 7. pipeline

## Goal

- create pipeline with python sdk

---

## Stack

- aws sagemaker
- sagemaker v3 python sdk

---

## steps

| #   | steps                                              |
| --- | -------------------------------------------------- |
| 0   | create venv and pip install                        |
| 1   | process data: load and split                       |
| 2   | train: train model                                 |
| 3   | evaluate: eval model to meet the minimun threhold; |
| 4   | export model: onnx                                 |
| 5   | parity check                                       |
| 6   | register model if all pass                         |
