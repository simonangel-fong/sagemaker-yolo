"""
MLflow helpers.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import mlflow

METRIC_KEY = "metrics/mAP50-95B"


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
                    # ultralytics picks save_dir itself, so record where the
                    # weights actually landed rather than rebuilding the path
                    "save_dir": str(trained.save_dir),
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


HYPERPARAMS_SCHEMA = 1

# Notebook/runtime concerns, not hyperparameters. `device` and `workers` follow
# the notebook instance; the pipeline trains on a different one and must pick
# its own. `model` is baked into the training image as YOLO_WEIGHTS.
NOT_HYPERPARAMS = frozenset(
    {"device", "workers", "project", "name", "exist_ok", "model"}
)


def export_hyperparams(
    path: Path,
    best_run: dict,
    base_cfg: dict,
    sweep_axes: dict,
    experiment: str,
    tracking_uri: str,
    metric: str = "mAP50-95",
    n_compared: int | None = None,
) -> Path:
    """
    Freeze the winning configuration to the file the train pipeline reads.

    This is the handoff between MLflow and the pipeline. The pipeline never
    queries the tracking server, so once this file is committed the server can
    be shut down and training still reproduces the winning run.

    `base_cfg` supplies the config the sweep held constant (imgsz, batch, seed);
    `best_run` supplies the axes it varied. Both are needed -- the swept axes
    alone are not a complete training configuration.
    """
    hyperparameters = {
        key: value
        for key, value in {**base_cfg, **{k: best_run[k] for k in sweep_axes}}.items()
        if key not in NOT_HYPERPARAMS
    }

    document = {
        "schema": HYPERPARAMS_SCHEMA,
        "hyperparameters": hyperparameters,
        "provenance": {
            "run_id": best_run["run_id"],
            "experiment": experiment,
            "tracking_uri": tracking_uri,
            "metric": metric,
            "value": round(best_run[metric], 4),
            "swept_axes": {k: list(v) for k, v in sweep_axes.items()},
            "runs_compared": n_compared if n_compared is not None else len(sweep_axes),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        },
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n")
    return path


def export_hyperparams_from_experiment(
    path: Path,
    experiment_name: str,
    base_cfg: dict,
    sweep_axes: dict,
    metric: str = "mAP50-95",
) -> Path:
    """
    Rebuild the hyperparameter file from the tracking server.

    Fallback for when the notebook session that ran the sweep is gone but the
    server is still up -- cheaper than re-running the sweep to regenerate a
    small JSON file. Requires the tracking server, unlike everything the
    pipeline does.
    """
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        raise RuntimeError(f"no experiment named {experiment_name!r}")

    metric_column = f"metrics.{METRIC_KEY}"
    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=[f"{metric_column} DESC"],
    )
    if runs.empty or metric_column not in runs.columns:
        raise RuntimeError(f"no runs with {METRIC_KEY} in {experiment_name!r}")

    runs = runs.dropna(subset=[metric_column])
    if runs.empty:
        raise RuntimeError(f"no runs with {METRIC_KEY} in {experiment_name!r}")

    winner = runs.iloc[0]
    # mlflow returns every param as a string; the axes decide the real type
    best_run = {"run_id": winner["run_id"], metric: float(winner[metric_column])}
    for axis, values in sweep_axes.items():
        raw = winner.get(f"params.{axis}")
        if raw is None:
            raise RuntimeError(f"run {winner['run_id']} has no param {axis!r}")
        best_run[axis] = type(list(values)[0])(raw)

    return export_hyperparams(
        path,
        best_run=best_run,
        base_cfg=base_cfg,
        sweep_axes=sweep_axes,
        experiment=experiment_name,
        tracking_uri=mlflow.get_tracking_uri(),
        metric=metric,
        n_compared=len(runs),
    )


# Floor is set from the run history: real 445-image runs land at 0.779-0.814,
MIN_MAP = 0.70

PROMOTION_MARGIN = 0.01


def check_export_parity(
    onnx_path: Path,
    data_yaml: Path,
    reference_map: float,
    tolerance: float = 0.01,
    imgsz: int = 640,
) -> dict:
    """
    Score the exported ONNX and compare it against the .pt metric.

    The gates run on metrics produced by the PyTorch weights, but what actually
    ships is the ONNX. `opset`/`simplify` can change numerics and still emit a
    file that loads cleanly, so the two are compared before anything registers.
    """
    from ultralytics import YOLO

    metrics = YOLO(str(onnx_path)).val(data=str(data_yaml), imgsz=imgsz, verbose=False)
    onnx_map = metrics.results_dict["metrics/mAP50-95(B)"]
    delta = abs(onnx_map - reference_map)

    return {
        "passed": delta <= tolerance,
        "onnx_map": onnx_map,
        "reference_map": reference_map,
        "delta": delta,
        "tolerance": tolerance,
    }


def register_model(
    run_id: str,
    onnx_path: Path,
    name: str,
    min_map: float = MIN_MAP,
    margin: float = PROMOTION_MARGIN,
    parity: dict | None = None,
    alias: str = "champion",
    model_name: str = "model",
) -> dict:
    """
    Gate a trained run, register it, and promote it only if it wins.

    Order is floor -> parity -> register -> promote. A run that fails a gate is
    tagged with the reason and left unregistered, so the failure is visible in
    the UI without cluttering the registry with unusable versions.

    Promotion is decided here rather than by the caller, so every notebook goes
    through the same rule and a short debug run cannot take the alias from a
    better model.
    """
    # mlflow.onnx needs onnxruntime at log time, to validate session options
    import onnx

    client = mlflow.MlflowClient()
    score = client.get_run(run_id).data.metrics.get(METRIC_KEY)
    result: dict[str, object] = {"run_id": run_id, "score": score}

    def reject(reason: str) -> dict:
        client.set_tag(run_id, "gate.passed", "false")
        client.set_tag(run_id, "gate.reason", reason)
        return {**result, "registered": False, "promoted": False, "reason": reason}

    # floor: catches a collapsed run, a truncated download, a smoke run
    if score is None:
        return reject(f"no {METRIC_KEY} logged on the run")
    if score < min_map:
        return reject(f"mAP50-95 {score:.4f} below floor {min_map}")

    # parity: catches an export that silently diverged from the weights
    if parity is not None and not parity["passed"]:
        return reject(
            f"onnx/pt mAP differ by {parity['delta']:.4f} "
            f"(tolerance {parity['tolerance']})"
        )

    # log_model must run inside the run that produced the weights
    with mlflow.start_run(run_id=run_id):
        info = mlflow.onnx.log_model(
            onnx_model=onnx.load(str(onnx_path)),
            name=model_name,
            registered_model_name=name,
        )

    version = info.registered_model_version
    if version is None:
        return reject("log_model did not return a registered version")
    version = str(version)

    client.set_tag(run_id, "gate.passed", "true")
    result.update({"registered": True, "version": version, "info": info})

    # promote only on a clear win, so run-to-run noise cannot move the alias
    try:
        champion = client.get_model_version_by_alias(name, alias)
        # a version whose run was deleted cannot be scored, so it loses
        champion_score = (
            client.get_run(champion.run_id).data.metrics.get(METRIC_KEY, float("-inf"))
            if champion.run_id
            else float("-inf")
        )
    except Exception:  # no alias yet, this version takes it uncontested
        champion, champion_score = None, float("-inf")

    if score > champion_score + margin:
        client.set_registered_model_alias(name, alias, version)
        return {**result, "promoted": True, "champion_score": champion_score,
                "previous_version": champion.version if champion else None}

    return {
        **result,
        "promoted": False,
        "champion_score": champion_score,
        "champion_version": champion.version if champion else None,
        "reason": f"did not beat champion {champion_score:.4f} by {margin}",
    }


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


def tracking_uri(name_prefix: str = "sagemaker-yolo") -> str:
    """
    Tracking URI.

    On SageMaker the URI is the MLflow app ARN, looked up by name so the account
    id and region do not have to be hardcoded. The serverless app replaced the
    always-on tracking server, so apps are tried first; the server lookup stays
    as a fallback for accounts that have not migrated yet.

    MLFLOW_TRACKING_URI wins if set -- but a stale value pointing at a deleted
    tracking server yields a confusing 403 rather than a not-found, so an ARN
    for a resource of the wrong kind is ignored instead of trusted.
    """
    import boto3

    client = boto3.client("sagemaker")

    uri = os.environ.get("MLFLOW_TRACKING_URI")
    if uri and ":mlflow-tracking-server/" not in uri:
        return uri

    apps = client.list_mlflow_apps()["Summaries"]
    for app in apps:
        if app["Name"].startswith(name_prefix):
            return app["Arn"]

    servers = client.list_mlflow_tracking_servers()["TrackingServerSummaries"]
    for server in servers:
        if server["TrackingServerName"].startswith(name_prefix):
            return server["TrackingServerArn"]

    raise RuntimeError(
        f"no MLflow app or tracking server starting with {name_prefix!r}; "
        f"found apps {[a['Name'] for a in apps]} and "
        f"servers {[s['TrackingServerName'] for s in servers]}"
    )
