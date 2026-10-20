"""Model endpoints: pair calibration summaries, calibration, scoring."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.features import FEATURE_VERSION
from app.anomaly import service as anomaly_service
from app.core.errors import InvalidInput, NotFound
from app.core.pairs import resolve_pair_id
from app.db.session import get_session
from app.models.evaluation import ModelCalibration
from app.schemas.api import CalibrationOut, ScoreRequest

router = APIRouter(prefix="/model", tags=["model"])


class CalibrateRequest(BaseModel):
    train_start: date | None = None
    train_end: date | None = None
    threshold: float | None = None
    scale_floor_fraction: float | None = None


@router.get("/pairs/{pair_id}/training-summary")
def training_summary(pair_id: str, session: Session = Depends(get_session)):
    canonical = resolve_pair_id(pair_id)
    cal = session.execute(
        select(ModelCalibration).where(ModelCalibration.pair_id == canonical)
        .order_by(ModelCalibration.id.desc()).limit(1)
    ).scalars().first()
    if cal is None:
        raise NotFound(
            f"Pair '{canonical}' has never been calibrated. POST /model/pairs/{canonical}/calibrate first."
        )
    return {
        "pair_id": canonical,
        "algorithm_version": cal.algorithm_version,
        "feature_version": cal.feature_version,
        "train_start": cal.train_start,
        "train_end": cal.train_end,
        "cutoff_ts": cal.cutoff_ts,
        "training_observations": cal.n,
        "median": float(cal.median),
        "scale": float(cal.scale),
        "scale_method": cal.scale_method,
        "threshold": float(cal.threshold),
        "data_status_note": cal.data_status_note,
        "feature": anomaly_service.FEATURE_NAME,
    }


@router.post("/pairs/{pair_id}/calibrate", response_model=CalibrationOut)
def calibrate(pair_id: str, body: CalibrateRequest | None = None,
              session: Session = Depends(get_session)):
    canonical = resolve_pair_id(pair_id)
    body = body or CalibrateRequest()
    cal = anomaly_service.calibrate_pair(
        session,
        canonical,
        body.train_start,
        body.train_end,
        threshold=body.threshold or 3.5,
        scale_floor_fraction=body.scale_floor_fraction,
    )
    return cal


@router.post("/pairs/{pair_id}/score")
def score(pair_id: str, body: ScoreRequest, session: Session = Depends(get_session)):
    canonical = resolve_pair_id(pair_id)
    cal = anomaly_service.default_calibration(session, canonical)
    # Temporal integrity: scoring a date at/before train_end is allowed only if
    # that date is NOT a member of the training sample.
    row = anomaly_service.score_observation(
        session, canonical, body.observation_date, cal, value=body.value
    )
    from app.analytics.signals import evaluate_signal
    sig = evaluate_signal(session, row)
    detail = anomaly_service.score_detail_dict(session, row)
    detail["disposition"] = {
        "status": sig.status,
        "disposition": sig.disposition,
        "liquidity_status": sig.liquidity_status,
        "expiry_status": sig.expiry_status,
        "cost_status": sig.cost_status,
        "reason_codes": sig.reason_codes,
        "checks": sig.checks,
    }
    return detail
