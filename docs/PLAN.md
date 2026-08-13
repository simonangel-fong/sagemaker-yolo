# Stage 8. deployment

- create model in sagemaker
- create inference endpoint serverless
- test

## Goal

- create pipeline with python sdk

---

## Stack

- aws sagemaker
- terraform
- trained model:
  - s3:sagemaker-yolo-dev-0luf20/trains/models/tune-cpu-556img-640px-epochs30/
    - best.pt
    - tune-cpu-556img-640px-epochs30.metadata.json
    - tune-cpu-556img-640px-epochs30.onnx

---

## steps

| #   | steps                                              |
| --- | -------------------------------------------------- |
| 1   | create model in sagemaker via terraform            |
| 2   | create inference endpoint serverless via terraform |
| 3   | test                                               |
