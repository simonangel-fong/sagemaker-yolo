## Pipeline

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

## Run

Python 3.12; 3.13+ has no numpy wheels yet and tries to build from source.

```sh
py -3.12 -m venv .venv
python.exe -m pip install --upgrade pip
pip install -r requirements.txt

# get bucket



# print the definition, creates nothing
python pipeline/run.py --dry-run

# create the pipeline
python pipeline/run.py

# run it on 40 images first
python pipeline/run.py --execute --limit 40

# run it on all 556
python pipeline/run.py --execute

```

---

## Running off Studio (CI, a plain VM)

In Studio the role and bucket are ambient. Elsewhere nothing is, so three things
have to be supplied explicitly.

| Need       | Supply with                          | Notes                                                     |
| ---------- | ------------------------------------ | --------------------------------------------------------- |
| Region     | `AWS_REGION` or `--region`           | Required. Not optional even for `--dry-run`.                |
| Bucket     | `BUCKET` or `--bucket`               | `~/.sagemaker-yolo.env` is a Studio-side file, absent in CI. |
| Role       | `SAGEMAKER_ROLE_ARN` or `--role`     | `get_execution_role()` only works inside Studio.            |
| Credentials| OIDC role assumption                 | Prefer over long-lived keys.                                |

`--dry-run` still calls AWS (it resolves the default bucket and the image URI),
so credentials are needed even though it creates nothing.

The pipeline role needs `sagemaker:CreatePipeline`/`UpdatePipeline` (and
`StartPipelineExecution` for `--execute`), `s3:PutObject` on the bucket — the SDK
uploads `preprocess.py` and `src/` at definition time — plus `iam:PassRole` for
the execution role.

```yaml
# .github/workflows/pipeline.yml
permissions:
  id-token: write        # OIDC
  contents: read

jobs:
  upsert:
    runs-on: ubuntu-latest
    env:
      AWS_REGION: ca-central-1
      BUCKET: ${{ vars.BUCKET }}
      SAGEMAKER_ROLE_ARN: ${{ vars.SAGEMAKER_ROLE_ARN }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.CI_ROLE_ARN }}
          aws-region: ca-central-1
      - run: python pipeline/run.py --dry-run
```

Two gotchas that cost time locally and would cost more in CI:

- **Run from the repo root.** `preprocess.py` and `src/` are resolved relative to
  the working directory to dodge a Windows path bug in the SDK; on Linux either
  works, but the root is what is tested.
- **A partial install breaks imports.** The sagemaker v3 subpackages (`-core`,
  `-mlops`, `-serve`, `-train`) version independently and an interrupted install
  leaves them mismatched. A clean runner never hits this; a cached venv can.