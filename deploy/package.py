"""
Deployment step 0: package the trained model for SageMaker.

SageMaker will not read the loose files under trains/models/<run>/. It wants a
single model.tar.gz whose root holds the weights and whose code/ holds the
handler:

    model.tar.gz
      <run>.onnx
      <run>.metadata.json
      code/inference.py
      code/requirements.txt

Usage:
    python -m deploy.package                 # from models/, upload
    python -m deploy.package --dry-run       # build the tar, skip the upload
"""

from __future__ import annotations

import argparse
import tarfile
from pathlib import Path

from pipeline import config
from src import s3_sync

REPO = Path(__file__).resolve().parents[1]
CODE_DIR = Path(__file__).resolve().parent / "code"
DEFAULT_RUN = "tune-cpu-556img-640px-epochs30"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default=DEFAULT_RUN, help="model basename")
    parser.add_argument("--models-dir", default=str(REPO / "models"))
    parser.add_argument("--out", default=str(REPO / "deploy" / "build"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def build(run: str, models_dir: Path, out_dir: Path) -> Path:
    onnx = models_dir / f"{run}.onnx"
    metadata = models_dir / f"{run}.metadata.json"

    for required in (onnx, metadata):
        if not required.exists():
            raise RuntimeError(f"missing artifact: {required}")

    handler = CODE_DIR / "inference.py"
    requirements = CODE_DIR / "requirements.txt"
    for required in (handler, requirements):
        if not required.exists():
            raise RuntimeError(f"missing handler file: {required}")

    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / "model.tar.gz"

    # arcname is set explicitly on every member: a tar built on Windows would
    # otherwise carry backslash paths the Linux container cannot resolve
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(onnx, arcname=onnx.name)
        tar.add(metadata, arcname=metadata.name)
        tar.add(handler, arcname="code/inference.py")
        tar.add(requirements, arcname="code/requirements.txt")

    return archive


def main() -> None:
    args = parse_args()
    run = args.run

    archive = build(run, Path(args.models_dir), Path(args.out))
    size_mb = archive.stat().st_size / 1024 / 1024
    print(f"built        {archive}  ({size_mb:.1f} MB)")

    with tarfile.open(archive) as tar:
        for member in tar.getnames():
            print(f"  {member}")

    destination = f"s3://{config.BUCKET}/deploy/{run}"
    if args.dry_run:
        print(f"\ndry-run      would upload to {destination}/model.tar.gz")
        return

    written = s3_sync.upload_files([archive], destination)
    print(f"\nuploaded     {written[0]}")
    print("model_data_url for terraform ^")


if __name__ == "__main__":
    main()
