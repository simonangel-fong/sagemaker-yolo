```sh
py -m venv .venv -3.12
pip install sagemaker

python -m pipeline.run --dry-run
python -m pipeline.run --start --wait   # upsert + execute
```

SageMaker pipeline built with the v3 Python SDK. Covers plan steps 1-3
(process data, train, evaluate + gate).

## Layout

| Path                           | Role                                          |
| ------------------------------ | --------------------------------------------- |
| `pipeline/config.py`           | role ARN, bucket, region; env-var overridable |
| `pipeline/definition.py`       | the pipeline: parameters, steps, wiring       |
| `pipeline/run.py`              | upsert / start / dry-run CLI                  |
| `pipeline/steps/preprocess.py` | step 1 container entry point                  |
| `pipeline/steps/train.py`      | step 2 container entry point                  |
| `pipeline/steps/evaluate.py`   | step 3 container entry point                  |
| `pipeline/_windows_fix.py`     | SDK CRLF workaround, Windows only             |

`src/` is unchanged by the pipeline and still drives the notebooks. The steps
reuse it (`data_loader`, `train.collect_artifacts`) rather than reimplementing.

## Steps

```
ProcessData ──> TrainModel ──> EvaluateModel ──> CheckThreshold
                                                   ├─ pass: (steps 4-6)
                                                   └─ fail: FailStep
```

| Step             | Type       | Instance     | Notes                            |
| ---------------- | ---------- | ------------ | -------------------------------- |
| `ProcessData`    | Processing | ml.m5.xlarge | sklearn image; split + data.yaml |
| `TrainModel`     | Training   | ml.g5.xlarge | PyTorch GPU DLC + ultralytics    |
| `EvaluateModel`  | Processing | ml.m5.xlarge | PyTorch CPU image; re-scores     |
| `CheckThreshold` | Condition  | -            | gates on mAP50-95 >= MinMap      |

Steps are wired through `properties`, not literal S3 paths, so SageMaker infers
the dependency graph and a re-split cannot leave a later step on a stale prefix.

`EvaluateModel` re-scores `best.pt` rather than trusting the training job's own
`summary.json`. That is the point of the gate: it catches a checkpoint that does
not match its reported metrics. Both numbers land in `evaluation.json`.

## Parameters

| Name                     | Default           | Purpose                     |
| ------------------------ | ----------------- | --------------------------- |
| `RawDataUri`             | `s3://…/data/raw` | input images + labels       |
| `ProcessingInstanceType` | ml.m5.xlarge      | process + evaluate          |
| `ValFraction`            | 0.2               | val split size              |
| `Seed`                   | 0                 | split seed                  |
| `Limit`                  | 0                 | 0 = all pairs; >0 smoke run |
| `TrainingInstanceType`   | ml.g5.xlarge      | GPU for training            |
| `Epochs`                 | 10                |                             |
| `ImageSize`              | 640               |                             |
| `Batch`                  | 8                 |                             |
| `MinMap`                 | 0.70              | gate floor on mAP50-95      |

Override per execution without editing code:

```sh
python -m pipeline.run --start --wait --param Limit=40 --param Epochs=2
```

Always dry-run first. It renders the definition without touching AWS and is
where a bad parameter reference or a malformed S3 key surfaces.

## Caching

`CacheConfig` is enabled with a 7-day window, so re-running an unchanged step
reuses the previous job. Editing a step's entry point changes its source hash
and forces a re-run of that step and everything downstream.

## Notes

- No MLflow. The training job is self-contained and metrics live in
  `summary.json` / `evaluation.json`, so nothing depends on a tracking server.
- `ml.g4dn.xlarge` quota is 0 in this account and `ml.g5.xlarge` is 1, so
  training cannot run in parallel with a notebook holding the same instance.
- Authoring from Windows has several traps; see `_windows_fix.py` and run a
  dry-run before every execution.

---

iris.csv in S3
     ↓
ProcessingStep
     ├── train.csv
     └── validation.csv
            ↓
       TrainingStep
            ↓
       model.tar.gz
            ↓
     EvaluationStep
            ↓
      accuracy.json
            ↓
      ConditionStep
      accuracy >= 0.90?
          ↓ yes
      Register model