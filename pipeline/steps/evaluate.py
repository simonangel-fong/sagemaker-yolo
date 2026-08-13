"""
Pipeline step 3: evaluate the trained model against a minimum threshold.

Runs as a ProcessingStep entry point. The training step's model.tar.gz is
mounted as an input; this script extracts best.pt and re-scores it on the val
split rather than trusting the metrics the training job reported about itself.

Scoring independently is the point of the gate: it catches a checkpoint that
was saved wrong, a tarball that was truncated in transit, or a summary.json
that no longer matches the weights beside it.

The result is written to evaluation.json, which the pipeline reads through a
PropertyFile so a ConditionStep can branch on the score.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import yaml

# ultralytics writes settings into $HOME on first import and phones home for
# version checks; neither works reliably in a processing container
os.environ.setdefault("YOLO_CONFIG_DIR", "/tmp/ultralytics")
os.environ.setdefault("YOLO_OFFLINE", "true")
Path(os.environ["YOLO_CONFIG_DIR"]).mkdir(parents=True, exist_ok=True)

BASE = Path("/opt/ml/processing")

# the floor mirrors src/tracking.py's MIN_MAP: real 445-image runs land at
# 0.779-0.814, so 0.70 rejects a collapsed or smoke-sized run without being
# so tight that ordinary run-to-run variation trips it
DEFAULT_MIN_MAP = 0.70


def ensure_ultralytics() -> None:
    """
    Install ultralytics if the image does not already carry it.

    ScriptProcessor has no `requirements` hook the way SourceCode does, and the
    PyTorch DLC ships torch but not ultralytics. Installing from here keeps the
    step to one processor class; --no-deps protects the image's tuned torch
    build from being replaced by a generic wheel off PyPI.
    """
    try:
        import ultralytics  # noqa: F401
        return
    except ImportError:
        pass

    for args in (
        # ultralytics' declared runtime deps, minus torch/torchvision (the DLC
        # ships those built against its own CUDA) and minus what the DLC
        # already provides: numpy, pillow, pyyaml, requests, matplotlib.
        # Checked against ultralytics 8.4's requires_dist -- dropping one here
        # turns into an ImportError several minutes into the job.
        ["pip", "install", "--no-cache-dir",
         "opencv-python-headless", "pandas", "seaborn", "psutil", "py-cpuinfo",
         "polars", "ultralytics-thop", "filelock", "nvidia-ml-py"],
        ["pip", "install", "--no-cache-dir", "--no-deps", "ultralytics>=8.3,<9"],
    ):
        subprocess.run([sys.executable, "-m", *args], check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", default=str(BASE / "model"))
    parser.add_argument("--split-dir", default=str(BASE / "split"))
    parser.add_argument("--config-dir", default=str(BASE / "config"))
    parser.add_argument("--output-dir", default=str(BASE / "evaluation"))
    parser.add_argument("--min-map", type=float, default=DEFAULT_MIN_MAP)
    parser.add_argument("--imgsz", type=int, default=640)
    # processing instances are CPU-only by default, which is fine for scoring
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def extract_model(model_dir: Path, dest: Path) -> Path:
    """Unpack model.tar.gz and return the path to best.pt."""
    dest.mkdir(parents=True, exist_ok=True)

    tarballs = sorted(model_dir.glob("*.tar.gz"))
    if not tarballs:
        # an uncompressed artifact is also valid, so only fail if neither exists
        loose = sorted(model_dir.rglob("best.pt"))
        if loose:
            return loose[0]
        raise RuntimeError(f"no model.tar.gz or best.pt under {model_dir}")

    with tarfile.open(tarballs[0]) as tf:
        tf.extractall(dest)

    weights = dest / "best.pt"
    if not weights.exists():
        raise RuntimeError(
            f"{tarballs[0].name} has no best.pt; contains "
            f"{sorted(p.name for p in dest.iterdir())}"
        )
    return weights


def resolve_data_yaml(config_dir: Path, split_dir: Path, dest: Path) -> Path:
    """Point data.yaml at the split as this container sees it."""
    cfg = yaml.safe_load((config_dir / "data.yaml").read_text())
    # as_posix(), not str(): on a Windows author machine str() yields
    # backslashes, which the Linux container cannot resolve
    cfg["path"] = split_dir.as_posix()
    dest.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return dest


def main() -> None:
    args = parse_args()

    model_dir = Path(args.model_dir)
    split_dir = Path(args.split_dir)
    config_dir = Path(args.config_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # name the missing channel explicitly; the alternative is a bare
    # FileNotFoundError on data.yaml several lines later
    for name, required in (("split", split_dir), ("config", config_dir)):
        if not required.exists():
            raise RuntimeError(f"{name} channel not found: {required}")

    weights = extract_model(model_dir, Path("/tmp/model"))
    print(f"weights      {weights} ({weights.stat().st_size / 1e6:.1f} MB)")

    data_yaml = resolve_data_yaml(config_dir, split_dir, Path("/tmp/data.yaml"))

    # after the checks above, so a missing model fails before the pip install
    ensure_ultralytics()

    from ultralytics import YOLO

    metrics = YOLO(str(weights)).val(
        data=str(data_yaml),
        imgsz=args.imgsz,
        device=args.device,
        plots=False,
        project="/tmp/runs",
        name="evaluate",
        exist_ok=True,
    )

    scored = {
        "mAP50": float(metrics.box.map50),
        "mAP50-95": float(metrics.box.map),
        "precision": float(metrics.box.mp),
        "recall": float(metrics.box.mr),
    }
    for key, value in scored.items():
        print(f"{key:12} {value:.4f}")

    passed = scored["mAP50-95"] >= args.min_map
    print(f"\ngate         mAP50-95 {scored['mAP50-95']:.4f} "
          f"{'>=' if passed else '<'} {args.min_map} -> "
          f"{'PASS' if passed else 'FAIL'}")

    # what the training job claimed, for comparison. A mismatch here means the
    # weights and the summary disagree, which is worth seeing even when the
    # gate passes.
    reported = None
    summary = Path("/tmp/model/summary.json")
    if summary.exists():
        reported = json.loads(summary.read_text()).get("val_metrics", {}).get("mAP50-95")
        if reported is not None:
            print(f"reported     {reported:.4f} "
                  f"(delta {abs(reported - scored['mAP50-95']):.4f})")

    # flat keys: JsonGet reads these by json_path from the ConditionStep
    (output_dir / "evaluation.json").write_text(
        json.dumps(
            {
                **scored,
                "passed": passed,
                "min_map": args.min_map,
                "reported_map50_95": reported,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
