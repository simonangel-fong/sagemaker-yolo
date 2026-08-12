"""
Pipeline step 2: train the model.

Runs as a TrainingStep entry point. SageMaker mounts each input channel under
/opt/ml/input/data/<channel> and uploads whatever is written to /opt/ml/model,
so this script only deals in local paths -- no S3 calls.

Hyperparameters arrive as --flags, sourced from pipeline parameters, so a run
can be re-executed with different values without editing this file.

No MLflow: metrics are written to summary.json in the model artifacts, which is
what the evaluate step reads.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml

# ultralytics writes settings into $HOME on first import and phones home for
# version checks; neither works reliably in a training container, so both are
# redirected/disabled before the import happens
os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/ultralytics")
os.environ.setdefault("YOLO_OFFLINE", "true")
Path(os.environ["YOLO_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)

# In the container this file sits at the top of the source dir with src/ beside
# it; in the repo it lives at pipeline/steps/, two levels down. Try both.
_here = Path(__file__).resolve().parent
for candidate in (_here, _here.parents[1]):
    if (candidate / "src").is_dir():
        sys.path.insert(0, str(candidate))
        break

from ultralytics import YOLO  # noqa: E402
from ultralytics.data.utils import check_det_dataset  # noqa: E402

from src.train import collect_artifacts  # noqa: E402

BASE = Path("/opt/ml")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split-dir", default=str(BASE / "input/data/split"))
    parser.add_argument("--config-dir", default=str(BASE / "input/data/config"))
    parser.add_argument("--model-dir", default=str(BASE / "model"))
    # ultralytics scratch space; not uploaded, so keep it off the model dir
    parser.add_argument("--run-dir", default="/tmp/runs")

    parser.add_argument("--model", default="yolo11n.pt")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    # "0" is the first GPU; "cpu" lets the step run on a cheap instance
    parser.add_argument("--device", default="0")
    return parser.parse_args()


def resolve_data_yaml(config_dir: Path, split_dir: Path, dest: Path) -> Path:
    """
    Point data.yaml at the split as this container sees it.

    The preprocess step writes an absolute `path`, which is only correct while
    the channel keeps the name it assumed. Rewriting it here means a renamed
    channel cannot silently train on the wrong directory.
    """
    cfg = yaml.safe_load((config_dir / "data.yaml").read_text())
    cfg["path"] = str(split_dir)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return dest


def main() -> None:
    args = parse_args()

    split_dir = Path(args.split_dir)
    config_dir = Path(args.config_dir)
    model_dir = Path(args.model_dir)

    # fail here rather than several minutes into training
    for required in (split_dir, config_dir):
        if not required.exists():
            raise RuntimeError(f"channel not found: {required}")

    data_yaml = resolve_data_yaml(config_dir, split_dir, Path("/tmp/data.yaml"))

    # confirms every image/label the descriptor promises is actually present
    checked = check_det_dataset(str(data_yaml))
    print(f"dataset      nc={checked['nc']} names={checked['names']}")

    cfg = {
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "seed": args.seed,
        "workers": args.workers,
        "device": args.device,
        "project": args.run_dir,
        "name": "train",
        "exist_ok": True,
    }
    print(f"config       {cfg}")

    model = YOLO(args.model)
    start = time.time()
    results = model.train(data=str(data_yaml), **cfg)
    elapsed = time.time() - start
    print(f"\nelapsed      {elapsed:.0f}s")

    save_dir = Path(results.save_dir)
    train_metrics = {
        key: results.results_dict[key]
        for key in (
            "metrics/precision(B)",
            "metrics/recall(B)",
            "metrics/mAP50(B)",
            "metrics/mAP50-95(B)",
        )
    }

    # re-score best.pt: the training metrics come from the final epoch, which is
    # not necessarily the checkpoint that ships
    best = YOLO(str(save_dir / "weights" / "best.pt"))
    scored = best.val(
        data=str(data_yaml),
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        plots=False,
        project=args.run_dir,
        name="val",
        exist_ok=True,
    )
    val_metrics = {
        "mAP50": scored.box.map50,
        "mAP50-95": scored.box.map,
        "precision": scored.box.mp,
        "recall": scored.box.mr,
    }

    for key, value in val_metrics.items():
        print(f"{key:12} {value:.4f}")

    # same artifact layout the notebooks produce, so downstream steps and local
    # runs read the same files
    collect_artifacts(
        model_dir,
        save_dir,
        {**cfg, "model": args.model},
        train_metrics,
        val_metrics,
    )

    # elapsed is not part of collect_artifacts' summary, so fold it in
    summary_path = model_dir / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["elapsed_seconds"] = round(elapsed)
    summary_path.write_text(json.dumps(summary, indent=2))

    print(f"\nartifacts    {sorted(p.name for p in model_dir.iterdir())}")


if __name__ == "__main__":
    main()
