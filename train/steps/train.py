# train.py

import argparse
import json
import os
import shutil

import torch
from ultralytics import YOLO

parser = argparse.ArgumentParser()
parser.add_argument("--epochs", type=int, default=10)
parser.add_argument("--imgsz", type=int, default=640)
parser.add_argument("--batch", type=int, default=8)
# GPU 0 when there is one, else cpu -- same script on a laptop and on ml.g5
parser.add_argument("--device", default=0 if torch.cuda.is_available() else "cpu")
args = parser.parse_args()

# data.yaml points at /opt/ml/input/data/split
data_yaml = "/opt/ml/input/data/config/data.yaml"

# baked pretrained
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
)

# persist
os.makedirs("/opt/ml/model", exist_ok=True)

best_pt = f"{results.save_dir}/weights/best.pt"
shutil.copy2(best_pt, "/opt/ml/model/best.pt")

# export: ONNX is the portable form the deploy pipeline serves
best = YOLO(best_pt)
onnx_path = best.export(
    format="onnx",
    imgsz=args.imgsz,
    opset=12,
    simplify=True,
)
shutil.copy2(onnx_path, "/opt/ml/model/model.onnx")

# code/ is what the inference toolkit looks for inside model.tar.gz, so the
# artifact is deployable as registered
code_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs("/opt/ml/model/code", exist_ok=True)

shutil.copy2(
    f"{code_dir}/inference.py",
    "/opt/ml/model/code/inference.py",
)
shutil.copy2(
    f"{code_dir}/requirements-inference.txt",
    "/opt/ml/model/code/requirements.txt",
)

# the sidecar tells the endpoint how to preprocess and label
with open("/opt/ml/model/model.metadata.json", "w") as f:
    json.dump(
        {
            "imgsz": args.imgsz,
            "names": [best.names[i] for i in sorted(best.names)],
            "metrics": {
                "mAP50": results.results_dict["metrics/mAP50(B)"],
                "mAP50-95": results.results_dict["metrics/mAP50-95(B)"],
                "precision": results.results_dict["metrics/precision(B)"],
                "recall": results.results_dict["metrics/recall(B)"],
            },
            "epochs": args.epochs,
        },
        f,
        indent=2,
    )

print(f"mAP50    {results.results_dict['metrics/mAP50(B)']:.4f}")
print(f"mAP50-95 {results.results_dict['metrics/mAP50-95(B)']:.4f}")
