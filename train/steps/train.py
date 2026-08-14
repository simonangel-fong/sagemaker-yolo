# train.py

import argparse
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
shutil.copy2(
    f"{results.save_dir}/weights/best.pt",
    "/opt/ml/model/best.pt",
)

print(f"mAP50    {results.results_dict['metrics/mAP50(B)']:.4f}")
print(f"mAP50-95 {results.results_dict['metrics/mAP50-95(B)']:.4f}")
