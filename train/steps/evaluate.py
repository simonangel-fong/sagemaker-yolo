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

# the pipeline's data.yaml hardcodes the training mount, and a processing job
# cannot mount there, so rewrite the path for this job's layout
with open("/opt/ml/processing/config/data.yaml") as f:
    names = [
        line.split(":", 1)[1].strip()
        for line in f.read().splitlines()
        if line.startswith("names:")
    ][0]

data_yaml = "/opt/ml/processing/data.yaml"

with open(data_yaml, "w") as f:
    f.write(
        "path: /opt/ml/processing/split\n"
        "train: train/images\n"
        "val: val/images\n"
        f"names: {names}\n"
    )

metrics = model.val(
    data=data_yaml,
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
