"""
MLflow helpers.
"""

from __future__ import annotations

import os
from pathlib import Path

import mlflow


def dataset_params(processed_dir: Path, raw_dir: Path | None = None) -> dict[str, object]:
    """
    Get hyperparameters from processed_dir
    """
    params: dict[str, object] = {}
    for split in ("train", "val"):
        images = list((processed_dir / split / "images").iterdir())
        labels = list((processed_dir / split / "labels").iterdir())
        boxes = sum(
            len([ln for ln in p.read_text().splitlines() if ln.strip()]) for p in labels
        )
        params[f"data.{split}_images"] = len(images)
        params[f"data.{split}_boxes"] = boxes

    total_images = params["data.train_images"] + params["data.val_images"]
    params["data.total_images"] = total_images
    if raw_dir is not None:
        # How much of the available data this run actually used.
        available = len([p for p in raw_dir.iterdir()
                        if p.suffix.lower() != ".txt"])
        params["data.available_images"] = available
        params["data.fraction_used"] = round(
            total_images / available, 3) if available else 0

    return params


def log_dataset_context(processed_dir: Path, raw_dir: Path | None = None, **extra) -> dict:
    """
    Log hyperparameters to mlflow 
    """
    params = dataset_params(processed_dir, raw_dir)
    params.update(extra)
    mlflow.log_params(params)
    return params


def run_sweep(
    grid: list[dict],
    base_cfg: dict,
    data_yaml: Path,
    processed_dir: Path,
    raw_dir: Path,
    experiment: str,
    run_name: callable = None,
) -> list[dict]:
    """
    Run sweep defined in `grid`
    """
    import os
    import time

    from ultralytics import YOLO

    # loop grid
    results = []
    for i, overrides in enumerate(grid, start=1):

        # load param
        cfg = {**base_cfg, **overrides}
        weights = cfg.pop("model")
        name = run_name(
            cfg) if run_name else "-".join(f"{k}{v}" for k, v in overrides.items())

        # define env var
        os.environ["MLFLOW_EXPERIMENT_NAME"] = experiment
        os.environ["MLFLOW_RUN"] = name
        os.environ["MLFLOW_KEEP_RUN_ACTIVE"] = "true"

        print(
            f"\n{'=' * 60}\n[{i}/{len(grid)}] {name}  {overrides}\n{'=' * 60}")
        start = time.time()
        try:
            # construct yolo model with param
            model = YOLO(weights)

            # train model, output performance metrics
            trained = model.train(data=str(data_yaml), **cfg)
            # log elapsed time
            elapsed = time.time() - start

            # log mlflow
            log_dataset_context(
                processed_dir, raw_dir, **{f"sweep.{k}": v for k, v in overrides.items()}
            )
            mlflow.log_metric("elapsed_seconds", elapsed)
            run_id = mlflow.active_run().info.run_id
            mlflow.end_run()  # terminate mlflow run

            # append result
            results.append(
                {
                    "name": name,
                    "run_id": run_id,
                    **overrides,
                    "mAP50": trained.results_dict["metrics/mAP50(B)"],
                    "mAP50-95": trained.results_dict["metrics/mAP50-95(B)"],
                    "elapsed_s": round(elapsed),
                }
            )
            print(f"[{i}/{len(grid)}] done in {elapsed:.0f}s")
        except Exception as exc:  # noqa: BLE001 - one bad config must not kill the sweep
            print(f"[{i}/{len(grid)}] FAILED: {exc}")
            if mlflow.active_run():
                mlflow.end_run(status="FAILED")
            results.append({"name": name, **overrides, "error": str(exc)})

    return results


def latest_run_id(experiment_name: str) -> str | None:
    """Most recent run in an experiment, so a finished run can be reopened."""
    # get experiment
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        return None
    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )
    return None if runs.empty else runs.iloc[0]["run_id"]


def compare_runs(experiment_name: str, metrics: list[str] | None = None):
    """
    compare experiment runs
    """
    # metrics
    metrics = metrics or [
        "metrics/mAP50B",
        "metrics/mAP50-95B",
        "metrics/precisionB",
        "metrics/recallB",
    ]

    # get experiment
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise RuntimeError(f"no experiment named {experiment_name!r}")

    # order runs
    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["attributes.start_time DESC"],
    )
    if runs.empty:
        return runs

    columns = ["tags.mlflow.runName", "params.epochs",
               "params.imgsz", "params.data.train_images"]
    columns += [f"metrics.{m}" for m in metrics]
    present = [c for c in columns if c in runs.columns]
    table = runs[present].copy()
    table.columns = [c.split(".", 1)[-1] for c in present]
    return table


def tracking_uri() -> str:
    """Gat tracking URI."""
    return os.environ.get("MLFLOW_TRACKING_URI") or mlflow.get_tracking_uri()
