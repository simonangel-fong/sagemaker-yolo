"""
Pipeline step 1: build the train/val split.

Runs as a ProcessingStep entry point. SageMaker mounts the raw data at
/opt/ml/processing/input and uploads whatever is written to the output
directories, so this script only deals in local paths -- no S3 calls.

data.yaml is written to its own output channel because the training step
consumes it from a different mount point than the split itself.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# src/ is mounted here in the container; fall back to the repo when run locally
for candidate in ("/opt/ml/processing/code", str(Path(__file__).resolve().parents[2])):
    if (Path(candidate) / "src").is_dir():
        sys.path.insert(0, candidate)
        break

from src.data_loader import (
    CLASSES_FILENAME,
    build_split,
    summarize,
    verify_split,
    write_data_yaml,
)

BASE = Path("/opt/ml/processing")


def clear_dir(path: Path) -> None:
    """
    Empty a directory without removing the directory itself.

    Keeps a re-run idempotent when `path` is a mount point, where rmtree on the
    directory itself raises OSError "Device or resource busy".
    """
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default=str(BASE / "input"))
    parser.add_argument("--split-dir", default=str(BASE / "split"))
    parser.add_argument("--config-dir", default=str(BASE / "config"))
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=0)
    # 0 means every pair, since the pipeline parameter cannot pass None
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    limit = args.limit or None

    raw = Path(args.input_dir)
    split_dir = Path(args.split_dir)
    config_dir = Path(args.config_dir)

    # fail here rather than midway through the split
    if not raw.exists():
        raise RuntimeError(f"input dir not found: {raw}")

    stats = summarize(raw)
    print(f"pairs        {stats['pairs']}")
    print(f"boxes total  {stats['boxes_total']}")
    print(f"orphans      {len(stats['orphan_images'])} img, "
          f"{len(stats['orphan_labels'])} lbl")

    # malformed labels poison training silently, so stop the pipeline
    if stats["malformed"]:
        raise RuntimeError(
            f"{len(stats['malformed'])} malformed labels, first few: "
            f"{stats['malformed'][:5]}"
        )

    # split_dir is a bind mount here, so it cannot be removed and recreated --
    # clear what is inside it instead and leave the mount itself alone
    clear_dir(split_dir)

    counts = build_split(
        raw,
        split_dir,
        val_fraction=args.val_fraction,
        limit=limit,
        seed=args.seed,
        reset=False,
    )
    verified = verify_split(split_dir)
    print(f"split        train {counts['train']}, val {counts['val']}")

    # the training container mounts the split at a fixed path, which is not
    # where it sits now, so data.yaml points at the destination
    names = (raw / CLASSES_FILENAME).read_text().split()
    data_yaml = write_data_yaml(
        config_dir / "data.yaml", Path("/opt/ml/input/data/split"), names
    )
    print(f"classes      {names}")

    # a manifest makes the step's result inspectable without opening the split
    (config_dir / "preprocess.json").write_text(
        json.dumps(
            {
                "train": counts["train"],
                "val": counts["val"],
                "verified": verified,
                "boxes_total": stats["boxes_total"],
                "names": names,
                "seed": args.seed,
                "val_fraction": args.val_fraction,
                "limit": limit,
            },
            indent=2,
        )
    )
    print(f"\n{data_yaml.read_text()}")


if __name__ == "__main__":
    main()
