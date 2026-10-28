"""One-command training workflow.

    python -m ml.train_model --sync-history --mode daily

What it does, in order, with NO fabricated data:
1. Collect authorized/configured history via backend adapters (mcx bhavcopy
   when enabled; TrueData/AccelPix only with credentials) into
   ProviderDailyBar. Sources that cannot be reached are declared, never
   invented.
2. Build the validated pair dataset (ml.dataset) and FAIL with an actionable
   error when verified history is too thin for training.
3. Evaluate candidates chronologically and pick the most stable.
4. Fit the final pipeline on the presumed-normal partition; save a .joblib
   bundle atomically (tmp + os.replace) into ml/artifacts/.
5. Register metadata/lineage/checksum/evaluation in the DB and activate it.
6. Print a truthful summary; exit NON-ZERO when validation failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

# CLI runs from the repo root (`python -m ml.train_model`); make the backend
# package (app.*) importable regardless of the caller's working directory.
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
REPORT_DIR = Path(__file__).resolve().parent / "reports"

from ml import inference, jobs  # noqa: E402
from ml.dataset import TrainDataError, dataset, feature_matrix, fingerprint  # noqa: E402
from ml.features import BUNDLE_VERSION, FEATURE_NAMES, FEATURE_VERSION  # noqa: E402
from ml.train import (  # noqa: E402
    TrainDataError as FitDataError,
    candidate_scores,
    fit_final_model,
    select_candidate,
)


def build_bundle(fitted: dict, feature_names, evaluation: dict, quality_report: dict,
                 data_sha: str, train_window, sample_counts) -> dict:
    """Complete versioned bundle: fitted pipeline + provenance + metrics."""
    import numpy as np
    import pandas as pd
    import sklearn

    return {
        "bundle_version": BUNDLE_VERSION,
        "mode": "daily",
        "feature_version": FEATURE_VERSION,
        "feature_names": list(feature_names),
        "pipeline": fitted["pipeline"],
        "algorithm": fitted["algorithm"],
        "algorithm_version": fitted["algorithm_version"],
        "threshold": fitted["threshold"],
        "contamination": fitted["contamination"],
        "severity_bands": {"high": 1.3},
        "training": {
            "train_start": train_window[0].isoformat() if train_window[0] else None,
            "train_end": train_window[1].isoformat() if train_window[1] else None,
            "sample_count": sample_counts[0],
            "train_sample_count": sample_counts[1],
        },
        "evaluation": evaluation,
        "quality_report": quality_report,
        "data_fingerprint": data_sha,
        "package_versions": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit-learn": sklearn.__version__,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def save_bundle_atomic(bundle: dict, model_version: str) -> tuple[str, str]:
    """Write a tmp file, fsync, then os.replace into the artifact directory."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    import joblib

    final = ARTIFACT_DIR / f"mcx_gold_{bundle['mode']}_{model_version}.joblib"
    fd, tmp_path = tempfile.mkstemp(dir=ARTIFACT_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            joblib.dump(bundle, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, final)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    sha = hashlib.sha256(final.read_bytes()).hexdigest()
    return str(final), sha


def register_model(session, bundle: dict, artifact_path: str, artifact_sha: str) -> str:
    """Insert/refresh the DB registry row (status=active) for this artifact."""
    from datetime import date as _date

    from sqlalchemy import select

    from app.models.ml_registry import TrainedModel

    model_version = (
        f"daily_{bundle['algorithm']}_{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
    )
    row = TrainedModel(
        model_version=model_version,
        mode=bundle["mode"],
        algorithm=bundle["algorithm"],
        algorithm_version=bundle["algorithm_version"],
        feature_version=bundle["feature_version"],
        artifact_path=artifact_path,
        artifact_sha256=artifact_sha,
        feature_names=list(bundle["feature_names"]),
        bundle_version=bundle["bundle_version"],
        train_start=_date.fromisoformat(bundle["training"]["train_start"])
        if bundle["training"]["train_start"] else None,
        train_end=_date.fromisoformat(bundle["training"]["train_end"])
        if bundle["training"]["train_end"] else None,
        sample_count=bundle["training"]["sample_count"],
        train_sample_count=bundle["training"]["train_sample_count"],
        thresholds={
            "threshold": bundle["threshold"],
            "contamination": bundle["contamination"],
            "severity_bands": bundle["severity_bands"],
        },
        evaluation=bundle["evaluation"],
        quality_report=bundle["quality_report"],
        package_versions=bundle["package_versions"],
        data_fingerprint=bundle["data_fingerprint"],
        status="active",
        notes="registered by ml.train_model CLI",
        activated_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.commit()
    return model_version


def train_flow(session, sync_history: bool, days: int) -> int:
    print("[1/5] collecting authorized history...")
    if sync_history:
        from ml import data_sources

        sync = data_sources.sync_official_history(session, days=days)
        print(json.dumps(sync, indent=2, default=str))

    print("[2/5] building validated dataset...")
    try:
        ds = dataset(session)
    except TrainDataError as exc:
        print(f"FAILED: {exc}")
        return 2
    X, meta, names = feature_matrix(ds["blocks"])
    data_sha = fingerprint(ds["blocks"])
    windows = [m["trade_date"] for m in meta]
    train_start, train_end = min(windows), max(windows)
    print(f"    rows={len(X)} window={train_start}..{train_end} sha={data_sha[:12]}")

    print("[3/5] evaluating candidates (chronological walk-forward)...")
    candidates = candidate_scores(X)
    selected = select_candidate(candidates)
    print(f"    selected={selected} (stability-aware)")

    print("[4/5] fitting final pipeline on the presumed-normal partition...")
    try:
        fitted = fit_final_model(X, selected)
    except FitDataError as exc:
        print(f"FAILED: {exc}")
        return 3

    holdout_z = [m["rolling_z_20"] for m in meta[-max(1, len(meta) // 5):]]
    holdout_X = X[-max(1, len(X) // 5):]
    model_flags = []
    for vec in holdout_X:
        raw = float(-fitted["pipeline"].score_samples([vec])[0])
        model_flags.append(1 if raw >= fitted["threshold"] else 0)
    holdout_rate = (sum(model_flags) / len(model_flags)) if model_flags else None
    from ml.evaluate import evaluate

    evaluation = evaluate(candidates, selected, holdout_z, holdout_rate)

    print("[5/5] saving artifact + registering in the model registry...")
    bundle = build_bundle(
        fitted, FEATURE_NAMES, evaluation, ds["quality_report"], data_sha,
        (train_start, train_end),
        (len(X), fitted["train_rows"]),
    )
    try:
        saved_path, saved_sha = save_bundle_atomic(bundle, "stage")
        # Final immutable artifact name derives from the staged sha (same content).
        final_path, final_sha = save_bundle_atomic(bundle, saved_sha[:10])
        (ARTIFACT_DIR / f"mcx_gold_daily_stage.joblib").unlink(missing_ok=True)
        model_version = register_model(session, bundle, final_path, final_sha)
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: artifact save/registration error: {type(exc).__name__}: {exc}")
        return 4

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    Report = REPORT_DIR / f"train_{model_version}.json"
    Report.write_text(json.dumps({
        "model_version": model_version,
        "artifact_path": saved_path,
        "artifact_sha256": saved_sha,
        "bundle": {k: v for k, v in bundle.items() if k != "pipeline"},
    }, indent=2, default=str))

    print("--- SUMMARY ---")
    print(f"model_version={model_version}")
    print(f"artifact={final_path}")
    print(f"sha256={final_sha}")
    print(f"rows={len(X)} train_rows={fitted['train_rows']} "
          f"threshold={fitted['threshold']:.5f}")
    print(f"evaluation={json.dumps(evaluation, indent=2, default=str)}")
    print("sources: see the [1/5] report above for everything actually reached.")
    return 0


def status_flow(session) -> int:
    for mode in ("daily", "intraday"):
        st = inference.model_status(session, mode)
        print(json.dumps(st, indent=2, default=str))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="ml.train_model",
        description="Train the MCX Gold relative-value novelty model.",
    )
    parser.add_argument(
        "--sync-history", action="store_true",
        help="Collect configured/authorized source history before training.",
    )
    parser.add_argument(
        "--mode", default="daily", choices=["daily"],
        help="Scoring frequency. Intraday requires genuine licensed intraday "
             "history and cannot be trained from EOD bars.",
    )
    parser.add_argument(
        "--train-only", action="store_true",
        help="Skip sync; train from data already stored in the database.",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Print active/registry model status and exit.",
    )
    parser.add_argument(
        "--days", type=int, default=10,
        help="History sync lookback window in days (default 10).",
    )
    args = parser.parse_args(argv)

    # Configuration loads silently like the backend: no secrets are printed.
    from sqlalchemy.orm import sessionmaker

    from app.db.session import get_engine

    engine = get_engine()
    session = sessionmaker(bind=engine)()
    try:
        if args.status:
            return status_flow(session)
        if args.mode == "intraday":
            print("FAILED: intraday training requires genuine licensed intraday history; "
                  "EOD bars cannot train a tick-frequency model.")
            return 5
        return train_flow(session, sync_history=args.sync_history and not args.train_only,
                          days=args.days)
    finally:
        session.close()


def run_daily_job_cli() -> int:
    """Scheduled daily job entry point (cron / Task Scheduler safe)."""
    from sqlalchemy.orm import sessionmaker

    from app.db.session import get_engine

    engine = get_engine()
    session = sessionmaker(bind=engine)()
    try:
        summary = jobs.run_daily_job(session)
        print(json.dumps(summary, indent=2, default=str))
        return 0 if str(summary.get("status", "")).startswith("completed") else 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
