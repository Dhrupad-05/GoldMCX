"""ML operations endpoints: artifact status, scored anomalies, daily job.

The browser never touches the joblib file: status comes from trusted DB
registry metadata, anomaly results are stored rows, and the training/daily job
is a server-side workflow (CLI or admin-triggered POST), never local.
"""
from __future__ import annotations

import sys

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

# The root-level `ml/` package lives beside backend/; when uvicorn runs with
# the backend as cwd it is not on sys.path. Bootstrap it explicitly (idempotent).
from app.core.config import get_settings

_REPO_ROOT = str(get_settings().repo_root)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ml.inference import ModelUnavailable, model_status  # noqa: E402

from app.core.errors import InvalidInput, NotFound
from app.core.idempotency import (
    commit_result,
    idempotency_key_of,
    replay_or_claim,
    request_fingerprint,
)
from app.db.locking import locked
from app.db.session import get_session
from app.models.evaluation import AnomalyScore, SignalEvaluation
from app.models.source import IngestionRun

router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/status")
def get_model_status(session: Session = Depends(get_session), mode: str = "daily"):
    if mode not in ("daily", "intraday"):
        raise InvalidInput("mode must be 'daily' or 'intraday'")
    return model_status(session, mode)


@router.get("/latest-anomalies")
def latest_anomalies(
    session: Session = Depends(get_session),
    pair_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    q = select(AnomalyScore).order_by(AnomalyScore.observation_date.desc(), AnomalyScore.id.desc())
    if pair_id:
        q = q.where(AnomalyScore.pair_id == pair_id)
    rows = session.execute(q.limit(limit)).scalars().all()
    if not rows:
        return {
            "count": 0,
            "anomalies": [],
            "status": "NO_DATA",
            "note": ("No scored observations yet. Run the daily job (POST /ml/jobs/daily-run) "
                     "or the training CLI; no demo data is substituted."),
        }
    sig_by_score = {s.score_id: s for s in session.execute(select(SignalEvaluation)).scalars() if s.score_id}
    return {
        "count": len(rows),
        "status": "OK",
        "anomalies": [_score_dict(r, sig_by_score.get(r.id)) for r in rows],
    }


@router.get("/anomalies/{score_id}")
def anomaly_detail(score_id: int, session: Session = Depends(get_session)):
    row = session.get(AnomalyScore, score_id)
    if row is None:
        raise NotFound(f"Anomaly score {score_id} not found.")
    sig = session.execute(
        select(SignalEvaluation).where(SignalEvaluation.score_id == score_id)
    ).scalars().first()
    return _score_dict(row, sig)


def _score_dict(r: AnomalyScore, sig: SignalEvaluation | None) -> dict:
    return {
        "score_id": r.id,
        "pair_id": r.pair_id,
        "observation_date": r.observation_date,
        "feature": r.feature,
        "observed_value": float(r.observed_value),
        "robust_z": float(r.robust_z),
        "score": float(r.score),
        "is_anomaly": bool(r.is_anomaly),
        "severity": r.severity,
        "explanation": r.explanation,
        "warnings": r.warnings or [],
        "feature_values": r.feature_values or {},
        "data_status": r.data_status,
        "model_version": r.model_version,
        "disposition": None if sig is None else {
            "status": sig.status,
            "disposition": sig.disposition,
            "liquidity_status": sig.liquidity_status,
            "expiry_status": sig.expiry_status,
            "cost_status": sig.cost_status,
            "reason_codes": sig.reason_codes or [],
            "checks": sig.checks or [],
        },
    }


@router.post("/jobs/daily-run")
def trigger_daily_job(request: Request, session: Session = Depends(get_session)):
    """Admin: run the idempotent daily sync -> features -> scoring workflow."""
    _ensure_admin(request)
    route = "POST /api/v1/ml/jobs/daily-run"
    body = {"op": "daily_run"}
    body_hash = request_fingerprint(body)
    idem_key = idempotency_key_of(request)
    if idem_key:
        replay = replay_or_claim(session, route, idem_key, body_hash)
        if replay["payload"] is not None:
            return replay["payload"]

    from ml.jobs import run_daily_job

    with locked(session, "ml:daily_job"):
        summary = run_daily_job(session)

    if idem_key:
        commit_result(session, route, idem_key, body_hash, summary,
                      result_ref=summary.get("run_id"))
        session.commit()
    return summary


@router.get("/jobs")
def job_runs(session: Session = Depends(get_session), limit: int = Query(default=10, ge=1, le=50)):
    rows = session.execute(
        select(IngestionRun)
        .where(IngestionRun.mode == "daily_ml_job")
        .order_by(IngestionRun.started_at.desc())
        .limit(limit)
    ).scalars().all()
    return {
        "count": len(rows),
        "runs": [
            {
                "run_id": r.id,
                "status": r.overall_status,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
                "summary": r.counts or {},
                "errors": r.errors or [],
            }
            for r in rows
        ],
    }


def _ensure_admin(request: Request) -> None:
    from app.api.v1.routes.ingestion import ADMIN_TOKEN_HEADER

    if request.headers.get(ADMIN_TOKEN_HEADER):
        return
    if get_settings().app_env == "development":
        return
    raise InvalidInput(
        "Daily-job execution is admin-only outside development; "
        f"send the '{ADMIN_TOKEN_HEADER}' header.",
        status_code=403,
    )
