# config.py
# Pipeline constants and the hyperparameter contract.

from __future__ import annotations

import json
from pathlib import Path

# ##############################
# Paths
# ##############################
TRAIN_DIR = Path(__file__).resolve().parent
HYPERPARAMS_PATH = TRAIN_DIR / "hyperparams.json"

# the serving handler, injected into the model artifact by the packaging step
INFERENCE_DIR = TRAIN_DIR.parent / "inference"

# schema versions this module knows how to read
SUPPORTED_SCHEMAS = (1,)

# ##############################
# Metric keys
# ##############################
METRIC = "mAP50-95"
METRIC_ULTRALYTICS = "metrics/mAP50-95(B)"
METRIC_MLFLOW = "metrics/mAP50-95B"

# ##############################
# Gates
# ##############################
# Threhold to register.
MIN_MAP = 0.70

# ##############################
# Model package
# ##############################
MODEL_PACKAGE_GROUP = "sagemaker-yolo"

# ##############################
# S3 prefixes
# ##############################
PREFIX = "train-pipeline"
RAW_PREFIX = "raw-data"

# ##############################
# Instance types
# ##############################
PROCESS_INSTANCE_TYPE = "ml.m5.large"
TRAIN_INSTANCE_TYPE = "ml.g5.xlarge"

# ##############################
# Hyperparameters
# ##############################
# Required in every hyperparams.json.
REQUIRED_HYPERPARAMS = ("epochs", "imgsz", "batch")

# Sanity bounds.
BOUNDS = {
    "epochs": (1, 1000),
    "imgsz": (32, 4096),
    "batch": (1, 512),
}

# Default
DEFAULT_HYPERPARAMS = {"epochs": 10, "imgsz": 640, "batch": 8}

# How to regenerate the file, quoted in every failure below.
_REGENERATE = (
    "Regenerate it by running the sweep in "
    "notebook/03-train-mlflow-sweep.ipynb, which calls export_hyperparams()."
)


class HyperparamsError(RuntimeError):
    """hyperparams.json is missing, malformed, or out of range."""


def load_hyperparams(path: Path = HYPERPARAMS_PATH) -> tuple[dict, dict]:
    """
    Read and validate the hyperparameter contract.

    Returns (hyperparameters, provenance). 
    """
    # invalid path
    if not path.exists():
        raise HyperparamsError(f"{path} not found. {_REGENERATE}")

    # invalid json file
    try:
        document = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise HyperparamsError(f"{path} is not valid JSON: {exc}. {_REGENERATE}") from exc

    # invalid json object
    if not isinstance(document, dict):
        raise HyperparamsError(f"{path} must contain a JSON object. {_REGENERATE}")

    # invalid shcema
    schema = document.get("schema")
    if schema not in SUPPORTED_SCHEMAS:
        raise HyperparamsError(
            f"{path} has schema {schema!r}, expected one of {SUPPORTED_SCHEMAS}. "
            "The file was written by a different version of export_hyperparams()."
        )

    # invalid param
    hyperparams = document.get("hyperparameters")
    if not isinstance(hyperparams, dict) or not hyperparams:
        raise HyperparamsError(
            f"{path} has no 'hyperparameters' object. {_REGENERATE}"
        )

    # key param missing
    missing = [key for key in REQUIRED_HYPERPARAMS if key not in hyperparams]
    if missing:
        raise HyperparamsError(
            f"{path} is missing hyperparameters {missing}. {_REGENERATE}"
        )

    validated = {key: _check(path, key, value) for key, value in hyperparams.items()}

    # invalid provenance
    provenance = document.get("provenance", {})
    if not isinstance(provenance, dict):
        raise HyperparamsError(f"{path} has a non-object 'provenance'.")

    return validated, provenance


def _check(path: Path, key: str, value: object) -> object:
    """Validate one hyperparameter. Bools are rejected: in Python they are ints."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HyperparamsError(
            f"{path}: hyperparameter {key!r} is {value!r}, expected a number. "
            f"{_REGENERATE}"
        )

    if key in BOUNDS:
        low, high = BOUNDS[key]
        if not low <= value <= high:
            raise HyperparamsError(
                f"{path}: hyperparameter {key!r} is {value}, "
                f"outside the supported range {low}-{high}."
            )

    return value


def describe(hyperparams: dict, provenance: dict) -> str:
    """One-line summary for the pipeline log, so a run records its own origin."""
    settings = "  ".join(f"{k}={v}" for k, v in sorted(hyperparams.items()))
    run_id = provenance.get("run_id")
    if not run_id:
        return f"{settings}  (no provenance)"

    return (
        f"{settings}  "
        f"[{provenance.get('metric', METRIC)}="
        f"{provenance.get('value', '?')} "
        f"run {run_id[:8]} "
        f"exp {provenance.get('experiment', '?')}]"
    )
