# Plan - stage 7. pipeline

## Goal

- create train pipeline with python sdk
  - from read raw to model registration

---

## Stack

- AWS Sagemaker
- sagamaker python sdk

---

## Phases

| #   | Phase                                 |
| --- | ------------------------------------- |
| 1   | design pipeline, key steps            |
| 2   | create pipeline and test step by step |
| 3   | end-to-end run                        |

---

## Pipeline

No MLflow. SageMaker Model Registry only. Auto promotion, no human step.

| #   | Step           | Type           | In                        | Out                       |
| --- | -------------- | -------------- | ------------------------- | ------------------------- |
| 1   | Preprocess     | ProcessingStep | `data/raw`                | `data/split`, `data.yaml` |
| 2   | Train          | TrainingStep   | `data/split`, `data.yaml` | `best.pt`                 |
| 3   | Export         | ProcessingStep | `best.pt`                 | `model.onnx`, metadata    |
| 4   | Evaluate       | ProcessingStep | `model.onnx`, val split   | `evaluation.json`         |
| 5   | Quality gate   | ConditionStep  | `evaluation.json`         | continue / stop           |
| 6   | Register       | RegisterModel  | `model.onnx`, metrics     | package, PendingApproval  |
| 7   | Compare        | ProcessingStep | package, approved package | `promotion.json`          |
| 8   | Promotion gate | ConditionStep  | `promotion.json`          | continue / stop           |
| 9   | Promote        | ProcessingStep | package                   | status Approved           |

---

## Design notes

### Gates

- **Step 5** - `mAP50-95 >= 0.70`. Fails, nothing registers.
- **Step 8** - beats approved package by `0.01`. Fails, package stays PendingApproval.

Floor from run history: real 445-image runs score 0.779-0.814. Margin is a placeholder; confirm with three 445-image runs at seeds 0/1/2.

### Conventions

- Champion = most recent package with `ModelApprovalStatus=Approved`.
- Metrics ride with the package via `ModelMetrics` -> step 4 `evaluation.json`, so step 7 reads the incumbent score from the registry.
- Endpoint deploys from the approved package.

### Step boundaries

| Split | Reason                                                              |
| ----- | ------------------------------------------------------------------- |
| 1 / 2 | preprocess CPU, train GPU; cached split skips on config-only changes |
| 2 / 3 | export needs no GPU, isolates the fragile ONNX conversion            |
| 3 / 4 | evaluate scores the ONNX, so the gated number is the shipped number  |
| 4 / 5 | `ConditionStep` needs a property to read; `JsonGet` reads the mAP    |
| 6 / 7 | `ConditionStep` cannot query the registry, so the lookup is its own step |

### To settle before phase 2

- **Train step type**: real `TrainingStep` (Estimator, `SM_CHANNEL_*`) or ProcessingStep wrapping current code. Decides how steps 1 and 2 exchange data.
- **Package group name**: distinct from anything the notebooks register.

### New artifacts

`evaluation.json`, `promotion.json`, and per-step entry-point scripts. Nothing writes these today.
