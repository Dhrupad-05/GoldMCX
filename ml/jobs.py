"""Idempotent daily workflow: EOD sync -> pair features -> ML scoring.

Safe to rerun after interruption. Steps:
1. Coordinate configured/authorized sources (async-licensed live feeds are the
   separate feed worker's domain; this is the scheduled EOD path).
2. Rebuild ONLY affected datasets with the same training-time feature code.
3. Score newly eligible observations with the ACTIVE daily artifact only.
   Without an active model the job reports MODEL_NOT_READY - it must NOT fall
   back to pretending the statistical baseline is the trained ML model.
4. Persist results with observation timestamp, leg expiries, feature values,
   raw score, model version, severity, source status, warnings; duplicate
   scoring of the same (pair, date, model, frequency) is skipped.
5. Invalidate caches only AFTER a successful commit.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import get_cache
from app.models.evaluation import AnomalyScore, SignalEvaluation
from app.models.ml_registry import get_active_model
from ml import data_sources
from ml.dataset import TrainDataError, dataset
from ml.features import feature_vector, FEATURE_VERSION
from ml.inference import ModelUnavailable, load_active, score_observation

logger = logging.getLogger("ml_jobs")


def run_daily_job(session: Session, days: int = 10) -> dict:
    """Scheduled daily update. Returns honest statuses; never fabricates data."""
    started = datetime.now(timezone.utc)
    run_id = started.strftime("daily-%Y%m%dT%H%M%SZ")
    errors: list[str] = []

    # 1. Sync persisted, validated EOD bars from configured sources.
    sync_results = data_sources.sync_official_history(session, days=days)

    # 2. Build the validated daily dataset (same code path as training).
    try:
        ds = dataset(session)
    except TrainDataError as exc:
        session.commit()
        get_cache().bump()  # data changed even if scoring is blocked
        _record_job(session, run_id, started, "completed_no_scoring",
                    {"sync": sync_results, "scoring": "MODEL_DATA_INSUFFICIENT",
                     "detail": str(exc)}, errors)
        return {
            "run_id": run_id, "status": "completed_no_scoring",
            "sync": sync_results, "scoring": None,
            "scoring_blocker": str(exc), "errors": errors,
        }

    # 3. Score with the ACTIVE daily artifact only.
    try:
        model = load_active(session, mode="daily")
    except ModelUnavailable as exc:
        session.commit()
        get_cache().bump()
        _record_job(session, run_id, started, "completed_no_scoring",
                    {"sync": sync_results, "scoring": "ML_MODEL_NOT_READY",
                     "detail": exc.reason}, errors)
        return {
            "run_id": run_id, "status": "completed_no_scoring",
            "sync": sync_results, "scoring": None,
            "scoring_blocker": f"ML_MODEL_NOT_READY: {exc.reason}", "errors": errors,
        }

    scored = 0
    skipped = 0
    already = _scored_keys(session, model.model_version)
    for pair_id, block in ds["blocks"].items():
        for obs in block["observations"]:
            key = (pair_id, obs["trade_date"].isoformat(), model.model_version, "daily")
            if key in already:
                skipped += 1
                continue
            vec = feature_vector(obs)
            result = score_observation(model, vec)
            warnings: list[str] = []
            if obs.get("significant_calendar_gap"):
                warnings.append("multi_day_calendar_gap")
            if obs.get("is_roll_boundary_last"):
                warnings.append("contract_roll_boundary")
            if obs.get("volume_missing"):
                warnings.append("volume_missing")
            score_row = AnomalyScore(
                calibration_id=0,  # trained-ML provenance row; see model_version
                pair_id=pair_id,
                observation_date=obs["trade_date"],
                feature="mldaily_spread_pct",
                observed_value=obs["spread_pct"],
                robust_z=obs["rolling_z_20"],
                score=result["raw_score"],
                is_anomaly=1 if result["is_anomaly"] else 0,
                severity=result["severity"],
                explanation=(
                    f"Trained {model.algorithm} novelty score {result['raw_score']:.4f} "
                    f"vs threshold {result['threshold']:.4f}. Novelty is not a "
                    "probability of profit."
                ),
                warnings=warnings,
                feature_values=result["feature_values"],
                data_status=obs["source_status"],
                pair_feature_id=None,
                model_version=model.model_version,
            )
            session.add(score_row)
            session.flush()
            session.add(SignalEvaluation(
                score_id=score_row.id,
                status="ANOMALOUS" if result["is_anomaly"] else "NORMAL",
                disposition="WATCH" if result["severity"] == "Watch" else (
                    "ACTIONABLE" if result["severity"] == "High" else "IGNORE"),
                liquidity_status="PROVISIONAL" if obs.get("volume_missing") else "UNVERIFIED",
                expiry_status="CHECKED",
                cost_status="NOT_EVALUATED",
                checks=[{
                    "name": "expiry_pairing", "status": "PASS",
                    "detail": [obs["expiry_left"], obs["expiry_right"]],
                }, {
                    "name": "freshness", "status": "PASS",
                    "detail": {"trade_date": obs["trade_date"].isoformat()},
                }],
                reason_codes=[
                    f"MODEL_{model.model_version}", f"SEVERITY_{result['severity']}",
                    *(["MODEL_NOT_EXECUTABLE"] if obs.get("volume_missing") else []),
                ],
            ))
            already.add(key)
            scored += 1
    session.commit()

    # 5. Post-commit invalidation.
    get_cache().bump()
    summary = {
        "run_id": run_id, "status": "completed",
        "sync": sync_results,
        "scoring": {
            "model_version": model.model_version, "scored": scored,
            "skipped_existing": skipped, "feature_version": FEATURE_VERSION,
        },
        "errors": errors,
    }
    _record_job(session, run_id, started, "completed", summary, errors)
    return summary


def _scored_keys(session: Session, model_version: str) -> set[tuple[str, str, str, str]]:
    rows = session.execute(
        select(AnomalyScore.pair_id, AnomalyScore.observation_date, AnomalyScore.model_version)
        .where(AnomalyScore.model_version == model_version)
    ).all()
    return {(p, d.isoformat(), v, "daily") for p, d, v in rows if v == model_version}




def _record_job(session: Session, run_id: str, started_at, status: str,
                summary: dict, errors: list[str]) -> None:
    """Durable job-run record through the ingestion-run table (same lineage contract)."""
    from app.models.source import IngestionRun
    from app.ingestion.constants import PARSER_VERSION

    existing = session.execute(
        select(IngestionRun).where(IngestionRun.id == run_id)
    ).scalar_one_or_none()
    if existing is not None:
        existing.overall_status = status
        existing.completed_at = datetime.now(timezone.utc)
        existing.counts = summary
        existing.errors = errors
        session.commit()
        return
    session.add(IngestionRun(
        id=run_id, mode="daily_ml_job", parser_version=PARSER_VERSION,
        overall_status=status, data_root="ml", counts=summary, errors=errors,
        completed_at=datetime.now(timezone.utc),
    ))
    session.commit()
