"""Signals endpoints."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.signals import evaluate_signal
from app.core.errors import NotFound
from app.core.pairs import resolve_pair_id
from app.db.session import get_session
from app.models.evaluation import AnomalyScore, SignalEvaluation
from app.schemas.api import SignalDetail, SignalOut

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalOut])
def list_signals(
    pair: str | None = None,
    status: str | None = None,
    disposition: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    q = (
        select(SignalEvaluation, AnomalyScore)
        .join(AnomalyScore, SignalEvaluation.score_id == AnomalyScore.id)
        .order_by(AnomalyScore.observation_date.desc())
        .limit(limit)
        .offset(offset)
    )
    if pair:
        canonical = resolve_pair_id(pair)
        q = q.where(AnomalyScore.pair_id == canonical)
    if status:
        q = q.where(SignalEvaluation.status == status.upper())
    if disposition:
        q = q.where(SignalEvaluation.disposition == disposition.upper())
    if date_from:
        q = q.where(AnomalyScore.observation_date >= date_from)
    if date_to:
        q = q.where(AnomalyScore.observation_date <= date_to)
    rows = session.execute(q).all()
    out = []
    for sig, score in rows:
        out.append(SignalOut(
            id=sig.id,
            score_id=score.id,
            pair_id=score.pair_id,
            observation_date=score.observation_date,
            status=sig.status,
            disposition=sig.disposition,
            severity=score.severity,
            robust_z=float(score.robust_z),
            score=float(score.score),
            liquidity_status=sig.liquidity_status,
            expiry_status=sig.expiry_status,
            cost_status=sig.cost_status,
            reason_codes=sig.reason_codes or [],
            data_status=score.data_status,
        ))
    return out


@router.get("/{signal_id}", response_model=SignalDetail)
def signal_detail(signal_id: int, session: Session = Depends(get_session)):
    from app.anomaly.service import score_detail_dict

    row = session.get(SignalEvaluation, signal_id)
    if row is None:
        raise NotFound(f"Signal '{signal_id}' not found.")
    score = session.get(AnomalyScore, row.score_id)
    if score is None:
        raise NotFound("Underlying anomaly score missing.")
    base = score_detail_dict(session, score)
    cal = base["calibration"]
    return SignalDetail(
        id=row.id,
        score_id=score.id,
        pair_id=score.pair_id,
        observation_date=score.observation_date,
        status=row.status,
        disposition=row.disposition,
        severity=score.severity,
        robust_z=float(score.robust_z),
        score=float(score.score),
        liquidity_status=row.liquidity_status,
        expiry_status=row.expiry_status,
        cost_status=row.cost_status,
        reason_codes=row.reason_codes or [],
        data_status=score.data_status,
        observed_value=float(score.observed_value),
        explanation=score.explanation,
        warnings=score.warnings or [],
        feature_values=score.feature_values or {},
        checks=row.checks or [],
        calibration=cal,
    )
