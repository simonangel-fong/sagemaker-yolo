# evaluate.py

import json
import os
import tarfile

from ultralytics import YOLO

# ------------------------
# Load model
# ------------------------

model_tar = "/opt/ml/processing/model/model.tar.gz"

with tarfile.open(model_tar) as tar:
    tar.extractall("/opt/ml/processing/model")

model = YOLO("/opt/ml/processing/model/best.pt")


# ------------------------
# Evaluate on the val split
# ------------------------

# data.yaml hardcodes path: /opt/ml/input/data/split, so the split is mounted
# there rather than under /opt/ml/processing -- see the eval step in pipeline.py
metrics = model.val(
    data="/opt/ml/processing/config/data.yaml",
    imgsz=640,
    device="cpu",
    project="/opt/ml/processing/evaluation/runs",
    name="val",
    exist_ok=True,
)

report = {
    "mAP50": metrics.box.map50,
    "mAP50-95": metrics.box.map,
    "precision": metrics.box.mp,
    "recall": metrics.box.mr,
}

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
