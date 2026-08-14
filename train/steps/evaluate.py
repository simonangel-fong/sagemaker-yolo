# evaluate.py

import argparse
import json
import os
import tarfile

from ultralytics import YOLO

# ##############################
# Get parameters
# ##############################
parser = argparse.ArgumentParser()
# must match training, or the score does not describe the model that shipped
parser.add_argument("--imgsz", type=int, default=640)
args = parser.parse_args()

# ##############################
# Load model
# ##############################
model_tar = "/opt/ml/processing/model/model.tar.gz"

# extract
with tarfile.open(model_tar) as tar:
    tar.extractall("/opt/ml/processing/model")

# construct model with best weights
model = YOLO("/opt/ml/processing/model/best.pt")


# ##############################
# Evaluate on the val split
# ##############################
# get data.yaml file
with open("/opt/ml/processing/config/data.yaml") as f:
    names = [
        line.split(":", 1)[1].strip()
        for line in f.read().splitlines()
        if line.startswith("names:")
    ][0]

data_yaml = "/opt/ml/processing/data.yaml"

# write data.yaml
with open(data_yaml, "w") as f:
    f.write(
        "path: /opt/ml/processing/split\n"
        "train: train/images\n"
        "val: val/images\n"
        f"names: {names}\n"
    )

# evaluate
metrics = model.val(
    data=data_yaml,
    imgsz=args.imgsz,
    device="cpu",
    project="/opt/ml/processing/evaluation/runs",
    name="val",
    exist_ok=True,
)

# get metrics
# the ConditionStep reads "mAP50-95" out of this file by that exact name
report = {
    "mAP50": metrics.box.map50,
    "mAP50-95": metrics.box.map,
    "precision": metrics.box.mp,
    "recall": metrics.box.mr,
    "imgsz": args.imgsz,
}

# persist
os.makedirs(
    "/opt/ml/processing/evaluation",
    exist_ok=True,
)

with open(
    "/opt/ml/processing/evaluation/evaluation.json",
    "w",
) as f:
    json.dump(report, f, indent=2)

print(report)
