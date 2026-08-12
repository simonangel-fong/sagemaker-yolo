```sh
py -m venv .venv -3.12
pip install sagemaker

python -m pipeline.run --dry-run
python -m pipeline.run --start --wait   # upsert + execute
```
