"""
Training entry point.

build the split, write the dataset descriptor, train, validate.

Usage:
    python -m trainjob.train                          # configs/train.yaml as-is
    python -m trainjob.train --limit 200              # smoke run on 200 pairs
    python -m trainjob.train --epochs 3 --device cpu  # override hyperparameters
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from ultralytics import YOLO
from ultralytics.data.utils import check_det_dataset

from src.data_loader import build_split, verify_split, write_data_yaml

# Repo root: trainjob/train.py -> trainjob -> repo
ROOT = Path(__file__).resolve().parent.parent

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
TRAIN_CFG = ROOT / "configs" / "train.yaml"
DATA_YAML = ROOT / "configs" / "data.yaml"
ARTIFACTS = ROOT / "artifacts"

CLASSES_FILENAME = "classes.txt"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    # paths
    parser.add_argument("--raw", type=Path, default=RAW,
                        help="raw image/label directory")
    parser.add_argument("--processed", type=Path, default=PROCESSED,
                        help="split output directory")
    parser.add_argument("--config", type=Path, default=TRAIN_CFG,
                        help="hyperparameter file")
    parser.add_argument("--data-yaml", type=Path, default=DATA_YAML,
                        help="dataset descriptor to generate")
    parser.add_argument("--artifacts", type=Path, default=ARTIFACTS,
                        help="where to collect weights, metrics and plots")

    # split
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--limit", type=int, default=None,
                        help="cap the number of pairs, for a fast smoke run")
    parser.add_argument("--split-seed", type=int, default=0)
    parser.add_argument("--skip-split", action="store_true",
                        help="reuse the existing split instead of rebuilding it")

    # hyperparameter overrides; None means "leave configs/train.yaml alone"
    parser.add_argument("--model", default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--project", default=None)
    parser.add_argument("--name", default=None)

    return parser.parse_args(argv)


def load_train_cfg(config: Path, overrides: dict[str, object]) -> dict:
    """Hyperparameters from configs/train.yaml, with CLI overrides applied."""
    cfg = yaml.safe_load(config.read_text())
    cfg.update({k: v for k, v in overrides.items() if v is not None})
    return cfg


def prepare_data(args: argparse.Namespace) -> Path:
    """Build the split and write the dataset descriptor. Returns data.yaml path."""
    if args.skip_split:
        print("split       reused", verify_split(args.processed))
    else:
        counts = build_split(
            args.raw,
            args.processed,
            val_fraction=args.val_fraction,
            limit=args.limit,
            seed=args.split_seed,
        )
        print("split      ", counts)
        print("verified   ", verify_split(args.processed))

    names = (args.raw / CLASSES_FILENAME).read_text().split()
    data_yaml = write_data_yaml(args.data_yaml, args.processed, names)

    # Fail here rather than several minutes into training.
    checked = check_det_dataset(str(data_yaml))
    print("dataset    ", {k: checked[k] for k in ("nc", "names", "train", "val")})
    return data_yaml


def train(data_yaml: Path, cfg: dict) -> tuple[Path, dict]:
    """Train and return (save_dir, final-epoch validation metrics)."""
    cfg = dict(cfg)
    weights = cfg.pop("model")
    # `project` is relative in the config; anchor it to the repo, not the cwd.
    project = Path(cfg["project"])
    cfg["project"] = str(project if project.is_absolute() else ROOT / project)

    model = YOLO(weights)

    start = time.time()
    results = model.train(data=str(data_yaml), **cfg)
    print(f"\nelapsed: {time.time() - start:.0f}s")

    save_dir = Path(results.save_dir)
    metrics = {
        key: results.results_dict[key]
        for key in (
            "metrics/precision(B)",
            "metrics/recall(B)",
            "metrics/mAP50(B)",
            "metrics/mAP50-95(B)",
        )
    }
    return save_dir, metrics


def validate(save_dir: Path, data_yaml: Path, cfg: dict) -> dict:
    """Re-evaluate best.pt on the val split."""
    best_weights = save_dir / "weights" / "best.pt"
    best = YOLO(str(best_weights))
    # Without an explicit project, ultralytics writes to ./runs/detect --
    # relative to the working directory, which the pod cannot write to.
    metrics = best.val(
        data=str(data_yaml),
        imgsz=cfg["imgsz"],
        batch=cfg["batch"],
        device=cfg["device"],
        plots=False,
        project=str(save_dir.parent),
        name=f"{save_dir.name}-val",
        exist_ok=True,
    )
    return {
        "mAP50": metrics.box.map50,
        "mAP50-95": metrics.box.map,
        "precision": metrics.box.mp,
        "recall": metrics.box.mr,
    }


def collect_artifacts(
    artifacts_dir: Path,
    save_dir: Path,
    cfg: dict,
    train_metrics: dict,
    val_metrics: dict,
) -> Path:
    """
    Gather the run into one predictable directory.

    Ultralytics scatters its output across a save_dir whose name shifts with
    run collisions. Downstream steps -- mlflow, kserve -- need a fixed path,
    so the pieces worth keeping are copied to a layout that does not move:

        <artifacts>/best.pt        the trained weights
        <artifacts>/summary.json   config, metrics, provenance
        <artifacts>/plots/         curves and confusion matrices

    Returns the artifacts directory.
    """
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    best = save_dir / "weights" / "best.pt"
    shutil.copy2(best, artifacts_dir / "best.pt")

    plots = artifacts_dir / "plots"
    plots.mkdir(exist_ok=True)
    for plot in save_dir.glob("*.png"):
        shutil.copy2(plot, plots / plot.name)

    # results.csv is the per-epoch history; keep it for curve reconstruction.
    results_csv = save_dir / "results.csv"
    if results_csv.exists():
        shutil.copy2(results_csv, artifacts_dir / "results.csv")

    (artifacts_dir / "summary.json").write_text(
        json.dumps(
            {
                "weights": "best.pt",
                "weights_bytes": best.stat().st_size,
                "config": cfg,
                "train_metrics": train_metrics,
                "val_metrics": val_metrics,
                "save_dir": str(save_dir),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
    )
    return artifacts_dir


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    cfg = load_train_cfg(
        args.config,
        {
            "model": args.model,
            "epochs": args.epochs,
            "imgsz": args.imgsz,
            "batch": args.batch,
            "device": args.device,
            "workers": args.workers,
            "seed": args.seed,
            "project": args.project,
            "name": args.name,
        },
    )
    print("config     ", cfg)

    data_yaml = prepare_data(args)
    save_dir, train_metrics = train(data_yaml, cfg)

    print("\nsave_dir   ", save_dir)
    for key, value in train_metrics.items():
        print(f"{key:24} {value:.4f}")

    val_metrics = validate(save_dir, data_yaml, cfg)
    print()
    for key, value in val_metrics.items():
        print(f"{key:12} {value:.4f}")

    for weight in sorted((save_dir / "weights").glob("*.pt")):
        print(f"{weight.name:10} {weight.stat().st_size / 1e6:.1f} MB")

    artifacts = collect_artifacts(args.artifacts, save_dir, cfg,
                                  train_metrics, val_metrics)
    print("\nartifacts  ", artifacts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
