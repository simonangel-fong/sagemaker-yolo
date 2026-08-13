import os
import json
import tarfile
import joblib
import pandas as pd


# ------------------------
# Load model
# ------------------------

model_tar = "/opt/ml/processing/model/model.tar.gz"

with tarfile.open(model_tar) as tar:
    tar.extractall("/opt/ml/processing/model")

model = joblib.load(
    "/opt/ml/processing/model/model.joblib"
)


# ------------------------
# Load validation data
# ------------------------

validation_path = (
    "/opt/ml/processing/validation/validation.csv"
)

df = pd.read_csv(validation_path)

X = df.drop(columns=["target"])
y = df["target"]


# ------------------------
# Evaluate
# ------------------------

accuracy = model.score(X, y)

report = {
    "accuracy": accuracy
}

os.makedirs(
    "/opt/ml/processing/evaluation",
    exist_ok=True,
)

with open(
    "/opt/ml/processing/evaluation/evaluation.json",
    "w",
) as f:
    json.dump(report, f)

print(report)