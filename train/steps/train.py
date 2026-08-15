# train.py

import argparse
import json
import os
import shutil

import torch
from ultralytics import YOLO

# Not hyperparameters: SageMaker sets these, or train() takes them positionally.
RESERVED = {"data", "project", "name", "exist_ok", "provenance"}

# ##############################
# Get parameters
# ##############################
parser = argparse.ArgumentParser()
parser.add_argument("--epochs", type=int, default=10)
parser.add_argument("--imgsz", type=int, default=640)
parser.add_argument("--batch", type=int, default=8)
# GPU 0 when gpu
parser.add_argument("--device", default=0 if torch.cuda.is_available() else "cpu")
# which sweep run chose these values; recorded, never acted on
parser.add_argument("--provenance", default=None)
# a wider sweep passes extra keys (lr0, optimizer, ...); forward them to YOLO
args, unknown = parser.parse_known_args()


def parse_extra(tokens: list[str]) -> dict:
    """
    Turn leftover `--key value` pairs into ultralytics keyword arguments.

    SageMaker renders every hyperparameter as a string, so values are coerced
    back to int/float where they look numeric and left alone otherwise.
    """
    extra = {}
    for i in range(0, len(tokens) - 1, 2):
        key, value = tokens[i], tokens[i + 1]
        if not key.startswith("--"):
            continue
        key = key[2:].replace("-", "_")
        if key in RESERVED:
            continue
        try:
            extra[key] = int(value)
        except ValueError:
            try:
                extra[key] = float(value)
            except ValueError:
                extra[key] = value
    return extra


extra = parse_extra(unknown)
if extra:
    print(f"extra hyperparameters {extra}")

# ##############################
# Define model
# ##############################
# data.yaml mount points
data_yaml = "/opt/ml/input/data/config/data.yaml"

# construct pretrained
model = YOLO(os.environ["YOLO_WEIGHTS"])

# train
results = model.train(
    data=data_yaml,
    epochs=args.epochs,
    imgsz=args.imgsz,
    batch=args.batch,
    device=args.device,
    project="/opt/ml/output/runs",
    name="train",
    exist_ok=True,
    **extra,
)

# ##############################
# Export model
# ##############################
os.makedirs("/opt/ml/model", exist_ok=True)

best_pt = f"{results.save_dir}/weights/best.pt"
shutil.copy2(best_pt, "/opt/ml/model/best.pt")

# export ONNX
# end2end=True is already the YOLO26 default, but the handler decodes the shape
# it produces -- [1, 300, 6], NMS-free -- so pin it rather than inherit it
best = YOLO(best_pt)
onnx_path = best.export(
    format="onnx",
    imgsz=args.imgsz,
    opset=12,
    simplify=True,
    end2end=True,
)
shutil.copy2(onnx_path, "/opt/ml/model/model.onnx")

# the serving handler is not written here: the PackageYolo pipeline step injects
# code/inference.py into the artifact, so it can change without retraining

# ##############################
# Export metadate
# ##############################
metadata = {
    "imgsz": args.imgsz,
    # how to decode the ONNX output: True means [1, 300, 6], already filtered
    "end2end": True,
    "names": [best.names[i] for i in sorted(best.names)],
    "metrics": {
        "mAP50": results.results_dict["metrics/mAP50(B)"],
        "mAP50-95": results.results_dict["metrics/mAP50-95(B)"],
        "precision": results.results_dict["metrics/precision(B)"],
        "recall": results.results_dict["metrics/recall(B)"],
    },
    "epochs": args.epochs,
    "batch": args.batch,
    **({"extra": extra} if extra else {}),
}

# the sweep that chose these hyperparameters, so the artifact stays traceable
# once the MLflow tracking server is shut down
if args.provenance:
    try:
        metadata["provenance"] = json.loads(args.provenance)
    except json.JSONDecodeError:
        # provenance is a record, not an input; a bad value must not fail a
        # training job that already succeeded
        print(f"warning: --provenance is not valid JSON: {args.provenance[:200]}")

# the sidecar tells the endpoint how to preprocess and label
with open("/opt/ml/model/model.metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)

print(f"mAP50    {results.results_dict['metrics/mAP50(B)']:.4f}")
print(f"mAP50-95 {results.results_dict['metrics/mAP50-95(B)']:.4f}")
